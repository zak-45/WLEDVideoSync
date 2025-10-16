"""
a: zak-45
d: 01/08/2025
v: 1.0.0.0

The api.py file defines the backend API for the WLEDVideoSync application.
It uses the FastAPI framework, which is seamlessly integrated with NiceGUI, to expose a set of RESTful endpoints and
a WebSocket for real-time communication. The primary purpose of this API is to allow external applications
(like Chataigne, or any other script/program) to monitor, control, and interact with the core components of WLEDVideoSync,
namely the Desktop and Media casting objects.


Key Architectural Components

1. ApiData Class

This is a simple yet crucial class that acts as a singleton or a namespace.
Its sole purpose is to hold references to the live instances of Desktop, Media, Netdevice,
and the shared Queue that are created in mainapp.py.
Design Rationale: This pattern effectively decouples the API endpoint definitions from the main application logic.
The API functions don't need to import the core classes directly; they are given access to the live, stateful objects at
runtime. This is a clean way to manage state in a web application.

2. RESTful API Endpoints (@app.get, @app.put)

The API is well-structured using FastAPI's decorators and is logically grouped by tags, which makes the auto-generated
documentation at the /docs endpoint clean and easy to navigate.

Endpoint Groups & Functionality:
•Root & Status (/api, /api/shutdown):
•Provides basic application version and compilation info.
•Offers a way to gracefully shut down the entire application, including the system tray icon.


•Parameter & Attribute Control (/api/{class_name}/params, /api/{class_name}/update_attribute):
•all_params: An introspection endpoint to read all current settings (attributes) of a class (Desktop or Media).
It wisely excludes large data buffers (frame_buffer) to keep the response lightweight.
•update_attribute: A powerful and flexible endpoint to dynamically change any attribute of a class.
It includes strong type validation (for bool, int, list, str) and specific business logic checks
(e.g., validating IP addresses, multicast device lists, and capture methods).
This is the primary mechanism for remote configuration.


•Frame Buffer Interaction (/api/{class_name}/buffer/...):
•Allows external clients to query the number of captured frames.
•Provides a way to retrieve a specific captured frame as a base64 encoded image, which is excellent for remote previews.
•Includes endpoints to save a frame to disk, either as a standard image or as a creative ASCII art text file.

•Casting Control (/api/.../run_cast, /api/util/casts_info, /api/.../cast_actions):
•run_cast: A simple trigger to start the casting process for a class.
•util_casts_info: A sophisticated endpoint that communicates with all active casting threads via a shared queue
to gather real-time status information, including a current thumbnail image. This demonstrates a robust pattern for
inter-thread communication in a web context.
•cast_actions: Implements a command queue (cast_name_todo) for running threads. This allows for fine-grained,asynchronous
control over individual casts (e.g., stopping a specific stream, taking a snapshot, or changing an IP on the fly).


•Utilities (/api/util/...):
•Exposes many of the helper functions from utils.py and winutil.py through the API.
•This includes getting window titles, listing media devices, triggering a network scan, downloading YouTube videos,
and a critical blackout function to immediately stop all activity.


•Presets (/api/config/presets/...):
•Allows for the programmatic application of saved filter or cast presets, which is essential for automation and scene
changes from external controllers.

3. WebSocket Endpoint (/ws)

This endpoint provides a low-latency, persistent connection for real-time actions.

•Purpose: It's primarily designed for the cast_image action, which allows an image from the buffer to be streamed to a
DDP device at a specific FPS for a set duration. This is perfect for triggering short animations or specific visual cues.

•Protocol: It expects a well-defined JSON structure ({"action":{"type": "...", "param": {...}}}) and validates it.
It also checks the action type against a list of allowed actions from the configuration file, which is a good
security practice.

•Error Handling: It correctly handles disconnects and sends detailed error messages back to the client over the
WebSocket if something goes wrong.


"""

import ast
import traceback

from nicegui import app
from str2bool import str2bool
from fastapi import Path as PathAPI
from fastapi import HTTPException
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from queue import Empty


from src.net.ddp_queue import DDPDevice
from src.utl.multicast import MultiUtils as Multi
from src.gui.presets import load_filter_preset, load_cast_preset
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import ImageUtils
from src.utl.cv2utils import CV2Utils
from src.utl.actionutils import action_to_test

from src.utl.winutil import *

from configmanager import cfg_mgr, LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.api')
api_logger = logger_manager.logger

class_to_test = ['Desktop', 'Media', 'Netdevice']

"""
Receive obj from mainapp
"""
class ApiData:
    """Holds references to the main application objects for API access.

    This class acts as a singleton namespace to store live instances of Desktop, Media, Netdevice, and the shared Queue.
    It enables API endpoints to interact with the application's core components without direct imports or tight coupling.
    """
    Desktop = None
    Media = None
    Netdevice = None
    Queue = None

    def __init__(self, Desktop, Media, Netdevice, t_data_buffer):
        ApiData.Desktop = Desktop
        ApiData.Media = Media
        ApiData.Netdevice = Netdevice
        ApiData.Queue = t_data_buffer


"""
FastAPI
"""

@app.get("/api", tags=["root"])
async def read_api_root():
    """
        Status: provide WLEDVideoSync info
    """

    return {"info": Utils.compile_info()}


@app.get("/api/shutdown", tags=["root"])
async def shutdown_root():
    """
        Status: stop app
    """
    app.shutdown()
    # stop pystray
    if str2bool(cfg_mgr.app_config['put_on_systray']):
        from src.gui.wledtray import WLEDVideoSync_systray
        WLEDVideoSync_systray.stop()

    return {"shutdown": "done"}


@app.get("/api/{class_name}/params", tags=["params"])
async def all_params(
        class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}')):
    """Returns all current settings (attributes) of the specified class.

    This endpoint provides a dictionary of all parameters for the given class, excluding large image buffers for
    Desktop and Media.

    Args:
        class_name: The name of the class to introspect. Must be one of the allowed class names.

    Returns:
        dict: A dictionary containing all parameters of the class, with image buffers removed for Desktop and Media.
    """
    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    # to avoid delete param from the class, need to copy to another dict
    # remove images buffers
    return_data = dict(vars(class_obj))
    if class_name != 'Netdevice':
        return_data.pop('frame_buffer', None)
        return_data.pop('cast_frame_buffer', None)

    return {"all_params": return_data}


@app.put("/api/{class_name}/update_attribute", tags=["params"])
async def update_attribute_by_name(class_name: str, param: str, value: str):
    """Updates a specific attribute of a class instance with strong type validation.

    This endpoint allows dynamic modification of any attribute for Desktop, Media, or Netdevice classes, enforcing type
    checks and business logic constraints.

    Args:
        class_name: The name of the class whose attribute is to be updated.
        param: The attribute name to update.
        value: The new value to assign to the attribute.

    Returns:
        dict: A message indicating the result of the update operation.

    Raises:
        HTTPException: If the class or attribute is invalid, or if the value does not meet type or business logic
        requirements.
    """
    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    if not hasattr(class_obj, param):
        raise HTTPException(status_code=400,
                            detail=f"Invalid attribute name: {param}")

    # determine type from class attribute
    expected_type = type(getattr(class_obj, param))

    # main type validation
    if expected_type == bool:
        if str2bool(value) is None:
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' must be a boolean")
        else:
            value = str2bool(value)
    elif expected_type == int:
        if param != "viinput":
            if not isinstance(value, int) and not str(value).isdigit():
                raise HTTPException(status_code=400,
                                    detail=f"Value '{value}' for attribute '{param}' " f"must be an integer")
            value = int(value)
    elif expected_type == list:
        if value is None or value == '':
            value = []
        value = ast.literal_eval(str(value))
        if not isinstance(value, list):
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' must be a list")
    elif expected_type == str:
        if not isinstance(value, str):
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' must be a string")
    else:
        raise HTTPException(status_code=400,
                            detail=f"Unsupported attribute type '{expected_type}' for attribute '{param}'")

    # special case for viinput , str or int, depend on the entry, only for Media, Desktop all is str
    if param == 'viinput' and class_name == 'Media':
        try:
            value = int(value)
        except ValueError:
            api_logger.debug("viinput act as string only")

    # check valid IP
    if param == 'cast_devices':
        is_valid = Multi.is_valid_cast_device(str(value))
        if not is_valid:
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' not comply to list [(0,'IP'),...]")

    elif param == 'host':
        is_valid = Utils.validate_ip_address(value)
        if not is_valid:
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' must be IP address")

    elif param == 'capture_methode':
        if value not in ['mss', 'av']:
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' must be in ['mss', 'av']")

    # set new value to class attribute
    setattr(class_obj, param, value)
    return {"message": f"Attribute '{param}' updated successfully for : '{class_obj}'"}


@app.get("/api/{class_name}/buffer", tags=["buffer"])
async def buffer_count(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}')):
    """
        Retrieve frame buffer length from a class (image number)
    """
    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    return {"buffer_count": len(class_obj.frame_buffer)}


@app.get("/api/{class_name}/buffer/{number}", tags=["buffer"])
async def buffer_image(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}'),
                       number: int = 0):
    """Retrieve a specific image from the frame buffer as a base64-encoded string.

    This endpoint allows clients to fetch a single captured frame from the buffer of the specified class for preview or
    processing.

    Args:
        class_name: The name of the class whose buffer to access.
        number: The index of the image in the buffer to retrieve.

    Returns:
        dict: A dictionary containing the base64-encoded image.

    Raises:
        HTTPException: If the image number does not exist or an error occurs during encoding.
    """
    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    if number > len(class_obj.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_obj} ")

    try:
        img = ImageUtils.image_array_to_base64(class_obj.frame_buffer[number])
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Class name: {class_name} provide this error : {e}",
        ) from e

    return {"buffer_base64": img}


@app.get("/api/{class_name}/buffer/{number}/save", tags=["buffer"])
async def buffer_image_save(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}'),
                            number: int = 0):
    """
        Retrieve image number from buffer class, save it to default folder
    """
    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    if number > len(class_obj.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_name} ")

    try:
        await CV2Utils.save_image(class_obj, 'frame_buffer', number)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Class name: {class_name} provide this error : {e}",
        ) from e

    return {"buffer_save": True}


@app.get("/api/{class_name}/buffer/{number}/asciiart/save", tags=["buffer"])
async def buffer_image_save_ascii(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}'),
                                  number: int = 0):
    """
        Retrieve image number from buffer class, save it to default folder as ascii_art
    """
    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    if number > len(class_obj.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_name} ")

    try:
        await CV2Utils.save_image(class_obj, 'frame_buffer', number, ascii_art=True)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Class name: {class_name} provide this error : {e}",
        ) from e

    return {"buffer_save": True}


@app.get("/api/{class_name}/run_cast", tags=["casts"])
async def run_cast(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}')):
    """
      Run the cast() from {class_obj}
    """
    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    # run cast and pass the queue to share data
    class_obj.cast(shared_buffer=ApiData.Queue)

    return {"run_cast": True}


@app.get("/api/util/active_win", tags=["desktop"])
async def util_active_win():
    """
       Show title from actual active window
    """
    return {"window_title": await active_window()}


@app.get("/api/util/win_titles", tags=["desktop"])
async def util_win_titles():
    """
        Retrieve all titles from windows
    """
    return {"windows_titles": await windows_titles()}


@app.get("/api/util/device_list", tags=["media"])
async def util_device_list():
    """
        Show available devices
    """
    return {"device_list": Utils.dev_list}


@app.get("/api/util/device_list_update", tags=["media"])
async def util_device_list_update():
    """
        Update available devices list
    """
    status = "Ok" if await Utils.dev_list_update() else "Error"
    return {"device_list": status}


@app.get("/api/util/download_yt/{yt_url:path}", tags=["media"])
async def util_download_yt(yt_url: str):
    """
       Download video from Youtube Url
    """

    if 'youtu' not in yt_url:
        raise HTTPException(status_code=400,
                            detail=f"Looks like not YT url : {yt_url} ")

    try:

        await Utils.youtube_download(yt_url=yt_url, interactive=False)

    except Exception as e:
        api_logger.error(f'youtube error: {e}')
        raise HTTPException(
            status_code=400,
            detail=f"Not able to retrieve video from : {yt_url} {e}",
        ) from e
    return {"youtube": "ok"}


@app.get("/api/util/device_net_scan", tags=["network"])
async def util_device_net_scan():
    """
        Scan network devices with zeroconf
    """
    # run in non-blocking mode
    await run_in_threadpool(ApiData.Netdevice.discover)
    return {"net_device_list": "done"}


@app.get("/api/util/blackout", tags=["utility"])
async def util_blackout():
    """
        Put ALL ddp devices Off and stop all Casts
    """
    api_logger.warning('** BLACKOUT **')
    ApiData.Desktop.t_exit_event.set()
    ApiData.Media.t_exit_event.set()
    ApiData.Desktop.stopcast = True
    ApiData.Media.stopcast = True

    async def wled_off(class_name):
        await Utils.put_wled_live(class_name.host, on=False, live=False, timeout=1)
        if class_name.multicast:
            for cast_item in class_name.cast_devices:
                await Utils.put_wled_live(cast_item[1], on=False, live=False, timeout=1)

    if ApiData.Desktop.wled:
        await wled_off(ApiData.Desktop)
    if ApiData.Media.wled:
        await wled_off(ApiData.Media)

    return {"blackout": "done"}


@app.get("/api/util/casts_info", tags=["casts"])
async def util_casts_info(img: bool = False):
    """Collects and returns real-time status information from all active casting threads.

    This endpoint communicates with all running Desktop and Media cast threads to gather their current status,
    optionally including a thumbnail image.

    Args:
        img: If True, include a thumbnail image in the status information.

    Returns:
        dict: A dictionary containing sorted status information for each cast.
    """
    api_logger.debug('Request Cast(s) info')

    # clear
    child_info_data = {}
    child_list = []

    params = img

    # create casts lists
    for item in ApiData.Desktop.cast_names:
        child_list.append(item)
        ApiData.Desktop.cast_name_todo.append(
            f'{str(item)}||info||{params}||{str(time.time())}'
        )
    for item in ApiData.Media.cast_names:
        child_list.append(item)
        ApiData.Media.cast_name_todo.append(f'{str(item)}||info||{params}||{str(time.time())}')

    # request info from threads
    ApiData.Desktop.t_todo_event.set()
    ApiData.Media.t_todo_event.set()

    # use to stop the loop in case of
    # start_time = time.time()
    api_logger.debug(f'Need to receive info from : {child_list}')

    # iterate through all Cast Names
    for _ in child_list:
        # wait and get info dict from a thread
        try:
            data = ApiData.Queue.get(timeout=3)
            child_info_data |= data
            ApiData.Queue.task_done()
        except Empty:
            api_logger.error('Empty queue, but Desktop/Media cast names list not')
            break

    # sort the dict
    sort_child_info_data = dict(sorted(child_info_data.items()))

    ApiData.Desktop.t_todo_event.clear()
    ApiData.Media.t_todo_event.clear()
    api_logger.debug('End request info')

    return {"t_info": sort_child_info_data}


@app.get("/api/util/queues", tags=["casts"])
async def list_cast_queues():
    """
        Get all queues (SL) from Desktop cast
        These SharedList are based on numpy array (y,x,3)
    """
    client = Utils.attach_to_queue_manager()
    if client.connect():
        return {"queues": ast.literal_eval(client.get_shared_lists())}
    else:
        raise HTTPException(status_code=400, detail="No Queues defined in Desktop")


@app.get("/api/{class_name}/list_actions", tags=["casts"])
async def list_todo_actions(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}')):
    """
    List to do actions for a Class name
    :param class_name:
    :return:
    """
    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    if not hasattr(class_obj, 'cast_name_todo'):
        raise HTTPException(status_code=400, detail="Invalid attribute name")

    return {"actions": class_obj.cast_name_todo}


@app.put("/api/{class_name}/cast_actions", tags=["casts"])
def action_to_thread(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}'),
                     cast_name: str = None,
                     action: str = None,
                     params: str = 'None',
                     clear: bool = False,
                     execute: bool = False):
    """
    Add action to cast_name_todo for a specific Cast
    If clear, remove all to do
    :param params: params to pass to the action
    :param execute: instruct casts to execute action in to do list
    :param clear: Remove all actions from to do list
    :param class_name:
    :param cast_name:
    :param action:
    :return:
    """

    class_obj = None
    if validate_class(class_name):
        class_obj = get_class(class_name)

    if cast_name is not None and cast_name not in class_obj.cast_names:
        api_logger.error(f"Invalid Cast name: {cast_name}")
        raise HTTPException(status_code=400,
                            detail=f"Invalid Cast name: {cast_name}")

    if not hasattr(class_obj, 'cast_name_todo'):
        api_logger.error("Invalid attribute name")
        raise HTTPException(status_code=400, detail="Invalid attribute name")

    if clear:
        class_obj.cast_name_todo = []
        api_logger.debug(f" To do cleared for {class_obj}'")
        return {"message": f" To do cleared for {class_obj}'"}

    if action not in action_to_test and action is not None:
        api_logger.error(f"Invalid action name. Allowed : {str(action_to_test)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action name {action}. Allowed : {str(action_to_test)}",
        )

    if class_name == 'Desktop':
        class_obj.t_desktop_lock.acquire()
    elif class_name == 'Media':
        class_obj.t_media_lock.acquire()

    if not execute:
        if cast_name is None or action is None:
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            api_logger.error(f"Invalid Cast/Thread name or action not set")
            raise HTTPException(status_code=400,
                                detail=f"Invalid Cast/Thread name or action not set")
        else:
            class_obj.cast_name_todo.append(
                cast_name
                + '||'
                + action
                + '||'
                + str(params)
                + '||'
                + str(time.time())
            )
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            api_logger.debug(f"Action '{action}' added successfully to : '{class_obj}'")
            return {"message": f"Action '{action}' added successfully to : '{class_obj}'"}

    else:

        if cast_name is None and action is None:
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            class_obj.t_todo_event.set()
            api_logger.debug(f"Actions in queue will be executed")
            return {"message": "Actions in queue will be executed"}

        elif cast_name is None or action is None:
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            api_logger.error("Invalid Cast/Thread name or action not set")
            raise HTTPException(status_code=400,
                                detail="Invalid Cast/Thread name or action not set")

        else:

            class_obj.cast_name_todo.append(
                str(cast_name) + '||' + str(action) + '||' + str(params) + '||' + str(time.time()))
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            class_obj.t_todo_event.set()
            api_logger.debug(f"Action '{action}' added successfully to : '{class_obj} and execute is On'")
            return {"message": f"Action '{action}' added successfully to : '{class_obj} and execute is On'"}


@app.get("/api/config/presets/{preset_type}/{file_name}/{class_name}", tags=["presets"])
async def apply_preset_api(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}'),
                           preset_type: str = None,
                           file_name: str = None):
    """
    Apply preset to Class name from saved one
    :param preset_type:
    :param class_name:
    :param file_name: preset name
    :return:
    """

    if class_name not in class_to_test:
        raise HTTPException(status_code=400,
                            detail=f"Class name: {class_name} not in {class_to_test}")
    if preset_type not in ['filter', 'cast']:
        raise HTTPException(status_code=400,
                            detail=f"Type preset: {preset_type} unknown")

    if preset_type == 'filter':
        try:
            result = await load_filter_preset(class_name=class_name, interactive=False, file_name=file_name)
            if result is False:
                raise HTTPException(status_code=400,
                                    detail=f"Apply preset return value : {result}")
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Not able to apply preset : {e}"
            ) from e
    elif preset_type == 'cast':
        try:
            result = await load_cast_preset(class_name=class_name, interactive=False, file_name=file_name)
            if result is False:
                raise HTTPException(status_code=400,
                                    detail=f"Apply preset return value : {result}")
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Not able to apply preset : {e}"
            ) from e
    else:
        raise HTTPException(status_code=400,
                            detail=f"unknown error in preset API")

    return {"apply_preset_result": True}


"""
FastAPI WebSockets
"""

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WS image Cast (we use WebSocket to minimize delay)
    Main logic: check action name, extract params, execute func, return ws status
    see page ws/docs for help
    usage example:
    {"action":{"type":"cast_image", "param":{"image_number":0,"device_number":-1, "class_name":"Media"}}}
    """

    action = ''
    allowed_actions = cfg_mgr.ws_config['allowed-actions'].split(',')

    try:
        await websocket.accept()

        while True:
            data = await websocket.receive_json()

            if not Utils.validate_ws_json_input(data):
                ws_msg = 'WEBSOCKET: received data not compliant with expected format ({"action":{"type":"","param":{}}})'
                api_logger.error(ws_msg)
                raise ValueError(ws_msg)

            action = data["action"]["type"]
            params = data["action"]["param"]

            if action not in allowed_actions:
                ws_msg = 'WEBSOCKET: received data contains unexpected action'
                api_logger.error(ws_msg)
                raise ValueError(ws_msg)

            if action == 'cast_image':
                required_params = ["image_number", "device_number", "class_name"]
                for param in required_params:
                    if param not in params:
                        ws_msg = f'WEBSOCKET: missing required parameter: {param}'
                        api_logger.error(ws_msg)
                        raise ValueError(ws_msg)

                optional_params = {
                    "fps_number": (0, 60),
                    "duration_number": (0, None),
                    "retry_number": (0, 10)
                }

                for param, (min_val, max_val) in optional_params.items():
                    if param in params:
                        params[param] = max(min_val, min(params[param], max_val)) if max_val else max(min_val,
                                                                                                      params[param])

                if "buffer_name" in params:
                    params["buffer_name"] = params["buffer_name"]

            func_name_parts = action.split('.')
            if len(func_name_parts) == 2:
                all_func = globals().get(func_name_parts[0])
                if not all_func:
                    raise AttributeError(f'Module {func_name_parts[0]} not found')
                if my_func := getattr(all_func, func_name_parts[1], None):
                    result = await run_in_threadpool(my_func, **params)
                else:
                    raise AttributeError(f'Function {func_name_parts[1]} not found in {func_name_parts[0]}')
            elif len(func_name_parts) == 1:
                if my_func := globals().get(action):
                    result = await run_in_threadpool(my_func, **params)
                else:
                    raise AttributeError(f'Function {action} not found')
            else:
                raise ValueError(f'Invalid function name: {func_name_parts}')

            await websocket.send_json({"action": action, "result": "success", "data": result})

    except WebSocketDisconnect:
        api_logger.warning('ws closed')
    except Exception as e:
        error_msg = traceback.format_exc()
        api_logger.error(error_msg)
        await websocket.send_json({"action": action, "result": "internal error", "error": str(e), "data": error_msg})
        await websocket.close()


"""
helpers
"""
def validate_class(class_name):
    if class_name not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_name} not in {class_to_test}")
    return True

def get_class(class_name):
    try:
        class_obj = getattr(ApiData, class_name)
    except AttributeError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid class name: {class_name}"
        ) from e
    return class_obj


def init_wvs(metadata, mouthCues):
    api_logger.info('websocket connection initiated')
    api_logger.debug(metadata, mouthCues)


def cast_image(image_number,
                     device_number,
                     class_name,
                     fps_number=25,
                     duration_number=1000,
                     retry_number=0,
                     buffer_name='buffer'):
    """
        Cast one image from buffer to a cast device at FPS during duration in s and with retry of n retry_number

    :param buffer_name:
    :param class_name:
    :param image_number:
    :param device_number:
    :param fps_number:
    :param duration_number:
    :param retry_number:
    :return:
    """
    images_buffer = []
    class_obj = globals()[class_name]

    """
    on 10/04/2024: device_number come from list entry order (0...n)
    """

    api_logger.debug('Cast one image from buffer')
    api_logger.debug(f"image number: {image_number}")
    api_logger.debug(f"device number: {device_number}")
    api_logger.debug(f"FPS: {fps_number}")
    api_logger.debug(f"Duration (in ms):  {duration_number}")
    api_logger.debug(f"retry packet number:  {retry_number}")
    api_logger.debug(f"class name: {class_name}")
    api_logger.debug(f"Image from buffer: {buffer_name}")

    if device_number == -1:  # instruct to use IP from the class.host
        ip = class_obj.host
    else:
        try:
            ip = class_obj.cast_devices[device_number][1]  # IP is on 2nd position
        except IndexError:
            api_logger.error('No device set in Cast Devices list')
            return

    if ip == '127.0.0.1':
        api_logger.warning('WEBSOCKET: Nothing to do for localhost 127.0.0.1')
        return

    if buffer_name.lower() == 'buffer':
        images_buffer = class_obj.frame_buffer
    elif buffer_name.lower() == 'multicast':
        images_buffer = class_obj.cast_frame_buffer

    # we need to retrieve the ddp device created during settings and not create one each time ....
    find = False
    ddp = None
    for ddp_device in Utils.ddp_devices:
        if ddp_device._destination == ip:
            ddp = ddp_device
            find = True
            break
    if find is False:
        # create DDP device
        ddp = DDPDevice(ip)
        Utils.ddp_devices.append(ddp)

    start_time = time.time() * 1000  # Get the start time in ms
    end_time = start_time + duration_number  # Calculate the end time

    if class_obj.protocol == "ddp":
        while time.time() * 1000 < end_time:  # Loop until current time exceeds end time in ms
            # Send x frames here
            try:
                ddp.send_to_queue(images_buffer[image_number], retry_number)
                if fps_number != 0:
                    time.sleep(1 / fps_number)  # Sleep in s for the time required to send one frame
            except IndexError:
                api_logger.error(f'No image set for this index: {image_number}')
                return
    else:
        api_logger.warning('Not DDP')
