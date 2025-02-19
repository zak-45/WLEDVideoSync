"""
a: zak45
d: 02/04/2024
v: 1.0.0

CastAPI

Cast media to ddp device(s)

DESKTOP: cast your full screen or a window content
    capture frames

MEDIA: cast an image / video / capture device
    capture frames
    cast image with Websocket
    create matrix based on ddp devices... so cast to a BIG one

+
API: FastAPI, for integration with third party application (e.g. Chataigne)

Web GUI based on NiceGUI

# 27/05/2024: cv2.imshow with import av  freeze

"""

import time
import sys
import os
import traceback
import configparser
import queue
import cfg_load as cfg
from starlette.websockets import WebSocketDisconnect

from src.cst import desktop, media
from src.gui import niceutils as nice
import ast
import tkinter as tk

from asyncio import set_event_loop_policy,sleep,create_task
from threading import current_thread
from subprocess import Popen
from src.net.ddp_queue import DDPDevice
from pathlib import Path as PathLib
from src.utl.utils import CASTUtils as Utils, LogElementHandler
from src.utl.utils import HTTPDiscovery as Net
from src.utl.cv2utils import ImageUtils
from src.utl.cv2utils import CV2Utils
from src.gui.niceutils import LocalFilePicker
from src.utl.utils import ScreenAreaSelection as Sa
from src.utl.utils import YtSearch
from src.utl.utils import AnimatedElement as Animate
from src.utl.multicast import MultiUtils as Multi
from datetime import datetime
from str2bool import str2bool
from PIL import Image
from fastapi.openapi.utils import get_openapi
from fastapi import HTTPException, WebSocket
from fastapi import Path as PathAPI
from starlette.concurrency import run_in_threadpool
from nicegui import app, ui, native, run
from configmanager import ConfigManager
from src.utl.fontsmanager import FontPreviewManager
from src.utl.fontsmanager import FontSetApplication
from src.txt.coldtypemp import RUNColdtype

cfg_mgr = ConfigManager(logger_name='WLEDLogger.api')

Desktop = desktop.CASTDesktop()
Media = media.CASTMedia()
Netdevice = Net()

if sys.platform.lower() == 'win32':
    from asyncio import WindowsSelectorEventLoopPolicy
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

class_to_test = ['Desktop', 'Media', 'Netdevice']
action_to_test = ['stop', 'shot', 'info', 'close-preview', 'host', 'open-preview', 'reset', 'multicast']

app.debug = False
log_ui = None
server_port = None
server_ip = None

"""
When this env var exist, this mean run from the one-file compressed executable.
Load of the config is not possible, folder config should not exist yet.
This avoid FileNotFoundError.
This env not exist when run from the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:

    # load optional modules
    if str2bool(cfg_mgr.custom_config['player']) or str2bool(cfg_mgr.custom_config['system-stats']):
        pass

    #  validate network config
    server_ip = cfg_mgr.server_config['server_ip']
    if not Utils.validate_ip_address(server_ip):
        cfg_mgr.logger.error(f'Bad server IP: {server_ip}')
        sys.exit(1)

    server_port = cfg_mgr.server_config['server_port']

    if server_port == 'auto':
        server_port = native.find_open_port()
    else:
        server_port = int(cfg_mgr.server_config['server_port'])

    if server_port not in range(1, 65536):
        cfg_mgr.logger.error(f'Bad server Port: {server_port}')
        sys.exit(2)

"""
Actions to do at application initialization 
"""


async def init_actions():
    """ Done at start of app and before GUI available """

    cfg_mgr.logger.info(f'Main running {current_thread().name}')

    # Apply some default params only once
    if str2bool(cfg_mgr.app_config['init_config_done']) is not True:

        def on_ok_click():
            # Close the window when OK button is clicked
            root.destroy()

        # Create the main window
        root = tk.Tk()
        root.title("WLEDVideoSync Information")
        root.geometry("820x460")  # Set the size of the window
        root.configure(bg='#657B83')  # Set the background color

        # Apply default GUI / param , depend on platform
        """
        preview_proc = False
        native_ui = False
        native_ui_size = 1200, 720
        uvicorn = True
        """
        if sys.platform.lower() == 'win32':
            Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'preview_proc', 'False')
            Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'native_ui', 'True')
            Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'native_ui_size', '1200,720')
            Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'uvicorn', 'True')
        else:
            Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'preview_proc', 'True')
            Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'native_ui', 'False')
            Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'native_ui_size', '')
            Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'uvicorn', 'False')

        Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'init_config_done', 'True')

        # Define the window's contents
        info_text = "Some Params has changed.... restart your app"
        info_label = tk.Label(root, text=info_text, bg='#657B83', fg='white', justify=tk.LEFT)
        info_label.pack(padx=10, pady=10)

        # Create the OK button
        ok_button = tk.Button(root, text="Ok", command=on_ok_click, bg='gray', fg='white')
        ok_button.pack(pady=10)

        # Start the Tkinter event loop
        root.mainloop()

        sys.exit()

    # Apply presets
    try:
        if str2bool(cfg_mgr.preset_config['load_at_start']):
            if cfg_mgr.preset_config['filter_media'] != '':
                cfg_mgr.logger.debug(f"apply : {cfg_mgr.preset_config['filter_media']} to filter Media")
                await load_filter_preset('Media', interactive=False, file_name=cfg_mgr.preset_config['filter_media'])
            if cfg_mgr.preset_config['filter_desktop'] != '':
                cfg_mgr.logger.debug(f"apply : {cfg_mgr.preset_config['filter_desktop']} to filter Desktop")
                await load_filter_preset('Desktop', interactive=False, file_name=cfg_mgr.preset_config['filter_desktop'])
            if cfg_mgr.preset_config['cast_media'] != '':
                cfg_mgr.logger.debug(f"apply : {cfg_mgr.preset_config['cast_media']} to cast Media")
                await load_cast_preset('Media', interactive=False, file_name=cfg_mgr.preset_config['cast_media'])
            if cfg_mgr.preset_config['cast_desktop'] != '':
                cfg_mgr.logger.debug(f"apply : {cfg_mgr.preset_config['cast_desktop']} to cast Desktop")
                await load_cast_preset('Desktop', interactive=False, file_name=cfg_mgr.preset_config['cast_desktop'])

        # check if linux and wayland
        if sys.platform.lower() == 'linux' and os.getenv('WAYLAND_DISPLAY') is not None:
            cfg_mgr.logger.error('Wayland detected, preview should not work !!. Switch to X11 session if want to see preview.')

    except Exception as e:
        cfg_mgr.logger.error(f"Error on app startup {e}")

# to share data between threads and main
t_data_buffer = queue.Queue()  # create a thread safe queue


class CastAPI:
    dark_mode = False
    netstat_process = None
    charts_row = None
    player = None
    progress_bar = None
    cpu_chart = None
    video_slider = None
    media_button_sync = None
    slider_button_sync = None
    type_sync = 'none'  # none, slider , player
    last_type_sync = ''  # slider , player
    search_areas = []  # contains YT search
    media_cast = None
    media_cast_run = None
    desktop_cast = None
    desktop_cast_run = None
    total_frame = 0
    total_packet = 0
    ram = 0
    cpu = 0
    w_image = None
    windows_titles = {}


"""
FastAPI
"""


@app.get("/api", tags=["root"])
async def read_api_root():
    """
        Status: provide WLEDVideoSync info
    """

    return {"info": Utils.compile_info()}


@app.get("/api/{class_name}/params", tags=["params"])
async def all_params(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}')):
    """
        Retrieve all 'params/attributes' from a class
    """
    if class_name not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_name} not in {class_to_test}")
    class_params = vars(globals()[class_name])
    # to avoid delete param from the class, need to copy to another dict
    return_data = dict(class_params)
    if class_name != 'Netdevice':
        del return_data['frame_buffer']
        del return_data['cast_frame_buffer']

    return {"all_params": return_data}


@app.put("/api/{class_name}/update_attribute", tags=["params"])
async def update_attribute_by_name(class_name: str, param: str, value: str):
    """
        Update  attribute for a specific class name
    """
    if class_name not in class_to_test:
        raise HTTPException(status_code=400,
                            detail=f"Class name: {class_name} not in {class_to_test}")

    try:
        class_obj = globals()[class_name]
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid class name: {class_name}"
        ) from e

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

    # special case for viinput , str or int, depend on the entry
    if param == 'viinput':
        try:
            value = int(value)
        except ValueError:
            cfg_mgr.logger.debug("viinput act as string only")

    # check valid IP
    if param == 'host':
        is_valid = Utils.validate_ip_address(value)
        if not is_valid:
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' must be IP address")

    # check cast devices comply to [(0,'IP'), ... ]
    if param == 'cast_devices':
        is_valid = Multi.is_valid_cast_device(str(value))
        if not is_valid:
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' not comply to list [(0,'IP'),...]")

    # set new value to class attribute
    setattr(class_obj, param, value)
    return {"message": f"Attribute '{param}' updated successfully for : '{class_obj}'"}


@app.get("/api/{class_obj}/buffer", tags=["buffer"])
async def buffer_count(class_obj: str = PathAPI(description=f'Class name, should be in: {class_to_test}')):
    """
        Retrieve frame buffer length from a class (image number)
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")
    class_name = globals()[class_obj]

    return {"buffer_count": len(class_name.frame_buffer)}


@app.get("/api/{class_obj}/buffer/{number}", tags=["buffer"])
async def buffer_image(class_obj: str = PathAPI(description=f'Class name, should be in: {class_to_test}'),
                       number: int = 0):
    """
        Retrieve image number from buffer class, result base64 image
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")

    try:
        class_name = globals()[class_obj]
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid Class name: {class_obj}"
        ) from e

    if number > len(class_name.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_obj} ")

    try:
        img = ImageUtils.image_array_to_base64(class_name.frame_buffer[number])
    except Exception as b_error:
        raise HTTPException(
            status_code=400,
            detail=f"Class name: {class_obj} provide this error : {b_error}",
        ) from b_error

    return {"buffer_base64": img}


@app.get("/api/{class_obj}/buffer/{number}/save", tags=["buffer"])
async def buffer_image_save(class_obj: str = PathAPI(description=f'Class name, should be in: {class_to_test}'),
                            number: int = 0):
    """
        Retrieve image number from buffer class, save it to default folder
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")

    try:
        class_name = globals()[class_obj]
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid Class name: {class_obj}"
        ) from e

    if number > len(class_name.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_obj} ")

    try:
        await CV2Utils.save_image(class_name, 'frame_buffer', number)
    except Exception as b_error:
        raise HTTPException(
            status_code=400,
            detail=f"Class name: {class_obj} provide this error : {b_error}",
        ) from b_error

    return {"buffer_save": True}


@app.get("/api/{class_obj}/buffer/{number}/asciiart/save", tags=["buffer"])
async def buffer_image_save_ascii(class_obj: str = PathAPI(description=f'Class name, should be in: {class_to_test}'),
                                  number: int = 0):
    """
        Retrieve image number from buffer class, save it to default folder as ascii_art
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")

    try:
        class_name = globals()[class_obj]
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid Class name: {class_obj}"
        ) from e

    if number > len(class_name.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_obj} ")

    try:
        await CV2Utils.save_image(class_name, 'frame_buffer', number, ascii_art=True)
    except Exception as b_error:
        raise HTTPException(
            status_code=400,
            detail=f"Class name: {class_obj} provide this error : {b_error}",
        ) from b_error

    return {"buffer_save": True}


@app.get("/api/{class_obj}/run_cast", tags=["casts"])
async def run_cast(class_obj: str = PathAPI(description=f'Class name, should be in: {class_to_test}')):
    """
      Run the cast() from {class_obj}
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")
    try:
        my_obj = globals()[class_obj]
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid Class name: {class_obj}"
        ) from e

    # run cast and pass the queue to share data
    my_obj.cast(shared_buffer=t_data_buffer)

    return {"run_cast": True}


@app.get("/api/util/active_win", tags=["desktop"])
async def util_active_win():
    """
       Show title from actual active window
    """
    return {"window_title": Utils.active_window()}


@app.get("/api/util/win_titles", tags=["desktop"])
async def util_win_titles():
    """
        Retrieve all titles from windows
    """
    return {"windows_titles": Utils.windows_titles()}


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
    status = "Ok" if Utils.dev_list_update() else "Error"
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
        cfg_mgr.logger.error(f'youtube error: {e}')
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
    await run_in_threadpool(Netdevice.discover)
    return {"net_device_list": "done"}


@app.get("/api/util/blackout", tags=["utility"])
async def util_blackout():
    """
        Put ALL ddp devices Off and stop all Casts
    """
    cfg_mgr.logger.warning('** BLACKOUT **')
    Desktop.t_exit_event.set()
    Media.t_exit_event.set()
    Desktop.stopcast = True
    Media.stopcast = True

    async def wled_off(class_name):
        await Utils.put_wled_live(class_name.host, on=False, live=False, timeout=1)
        if class_name.multicast:
            for cast_item in class_name.cast_devices:
                await Utils.put_wled_live(cast_item[1], on=False, live=False, timeout=1)

    if Desktop.wled:
        await wled_off(Desktop)
    if Media.wled:
        await wled_off(Media)

    return {"blackout": "done"}


@app.get("/api/util/casts_info", tags=["casts"])
async def util_casts_info(img: bool = False):
    """
        Get info from all Cast Threads
        Generate image for preview if requested
    :param: img : False/true
    """
    cfg_mgr.logger.debug('Request Cast(s) info')

    # clear
    child_info_data = {}
    child_list = []
       
    params = img

    # create casts lists
    for item in Desktop.cast_names:
        child_list.append(item)
        Desktop.cast_name_todo.append(
            f'{str(item)}||info||{params}||{str(time.time())}'
        )
    for item in Media.cast_names:
        child_list.append(item)
        Media.cast_name_todo.append(f'{str(item)}||info||{params}||{str(time.time())}')

    # request info from threads
    Desktop.t_todo_event.set()
    Media.t_todo_event.set()

    # use to stop the loop in case of
    # start_time = time.time()
    cfg_mgr.logger.debug(f'Need to receive info from : {child_list}')

    # iterate through all Cast Names
    for _ in child_list:
        # wait and get info dict from a thread
        try:
            data = t_data_buffer.get(timeout=3)
            child_info_data |= data
            t_data_buffer.task_done()
        except queue.Empty:
            cfg_mgr.logger.error('Empty queue, but Desktop/Media cast names list not')
            break

    # sort the dict
    sort_child_info_data = dict(sorted(child_info_data.items()))

    Desktop.t_todo_event.clear()
    Media.t_todo_event.clear()
    cfg_mgr.logger.debug('End request info')

    return {"t_info": sort_child_info_data}


@app.get("/api/util/queues", tags=["casts"])
async def list_cast_queues():
    """
        Get all queues from Desktop cast
        These queues wait for an image in numpy array (y,x,3)
    """

    return {"queues":Desktop.queue_names}

@app.get("/api/{class_name}/list_actions", tags=["casts"])
async def list_todo_actions(class_name: str = PathAPI(description=f'Class name, should be in: {class_to_test}')):
    """
    List to do actions for a Class name
    :param class_name:
    :return:
    """
    if class_name not in class_to_test:
        raise HTTPException(status_code=400,
                            detail=f"Class name: {class_name} not in {class_to_test}")
    try:
        class_obj = globals()[class_name]
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid class name: {class_name}"
        ) from e

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

    if class_name not in class_to_test:
        cfg_mgr.logger.error(f"Class name: {class_name} not in {class_to_test}")
        raise HTTPException(status_code=400,
                            detail=f"Class name: {class_name} not in {class_to_test}")
    try:
        class_obj = globals()[class_name]
    except KeyError as e:
        cfg_mgr.logger.error(f"Invalid class name: {class_name}")
        raise HTTPException(
            status_code=400, detail=f"Invalid class name: {class_name}"
        ) from e

    if cast_name is not None and cast_name not in class_obj.cast_names:
        cfg_mgr.logger.error(f"Invalid Cast name: {cast_name}")
        raise HTTPException(status_code=400,
                            detail=f"Invalid Cast name: {cast_name}")

    if not hasattr(class_obj, 'cast_name_todo'):
        cfg_mgr.logger.error("Invalid attribute name")
        raise HTTPException(status_code=400, detail="Invalid attribute name")

    if clear:
        class_obj.cast_name_todo = []
        cfg_mgr.logger.debug(f" To do cleared for {class_obj}'")
        return {"message": f" To do cleared for {class_obj}'"}

    if action not in action_to_test and action is not None:
        cfg_mgr.logger.error(f"Invalid action name. Allowed : {str(action_to_test)}")
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
            cfg_mgr.logger.error(f"Invalid Cast/Thread name or action not set")
            raise HTTPException(status_code=400,
                                detail=f"Invalid Cast/Thread name or action not set")
        else:
            class_obj.cast_name_todo.append(str(cast_name) + '||' + str(action) + '||'  + str(params) + '||' + str(time.time()))
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            cfg_mgr.logger.debug(f"Action '{action}' added successfully to : '{class_obj}'")
            return {"message": f"Action '{action}' added successfully to : '{class_obj}'"}

    else:

        if cast_name is None and action is None:
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            class_obj.t_todo_event.set()
            cfg_mgr.logger.debug(f"Actions in queue will be executed")
            return {"message": "Actions in queue will be executed"}

        elif cast_name is None or action is None:
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            cfg_mgr.logger.error("Invalid Cast/Thread name or action not set")
            raise HTTPException(status_code=400,
                                detail="Invalid Cast/Thread name or action not set")

        else:

            class_obj.cast_name_todo.append(str(cast_name) + '||' + str(action) + '||' + str(params) + '||' + str(time.time()))
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            class_obj.t_todo_event.set()
            cfg_mgr.logger.debug(f"Action '{action}' added successfully to : '{class_obj} and execute is On'")
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

websocket_info = 'These are the websocket end point calls and result'

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
                cfg_mgr.logger.error(ws_msg)
                raise ValueError(ws_msg)

            action = data["action"]["type"]
            params = data["action"]["param"]

            if action not in allowed_actions:
                ws_msg = 'WEBSOCKET: received data contains unexpected action'
                cfg_mgr.logger.error(ws_msg)
                raise ValueError(ws_msg)

            if action == 'cast_image':
                required_params = ["image_number", "device_number", "class_name"]
                for param in required_params:
                    if param not in params:
                        ws_msg = f'WEBSOCKET: missing required parameter: {param}'
                        cfg_mgr.logger.error(ws_msg)
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
        cfg_mgr.logger.warning('ws closed')
    except Exception as e:
        error_msg = traceback.format_exc()
        cfg_mgr.logger.error(error_msg)
        await websocket.send_json({"action": action, "result": "internal error", "error": str(e), "data": error_msg})
        await websocket.close()


def init_wvs(metadata, mouthCues):
    cfg_mgr.logger.info('websocket connection initiated')
    cfg_mgr.logger.debug(metadata, mouthCues)


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

    cfg_mgr.logger.debug('Cast one image from buffer')
    cfg_mgr.logger.debug(f"image number: {image_number}")
    cfg_mgr.logger.debug(f"device number: {device_number}")
    cfg_mgr.logger.debug(f"FPS: {fps_number}")
    cfg_mgr.logger.debug(f"Duration (in ms):  {duration_number}")
    cfg_mgr.logger.debug(f"retry packet number:  {retry_number}")
    cfg_mgr.logger.debug(f"class name: {class_name}")
    cfg_mgr.logger.debug(f"Image from buffer: {buffer_name}")

    if device_number == -1:  # instruct to use IP from the class.host
        ip = class_obj.host
    else:
        try:
            ip = class_obj.cast_devices[device_number][1]  # IP is on 2nd position
        except IndexError:
            cfg_mgr.logger.error('No device set in Cast Devices list')
            return

    if ip == '127.0.0.1':
        cfg_mgr.logger.warning('WEBSOCKET: Nothing to do for localhost 127.0.0.1')
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
                cfg_mgr.logger.error(f'No image set for this index: {image_number}')
                return
    else:
        cfg_mgr.logger.warning('Not DDP')

"""
NiceGUI
"""


@ui.page('/')
async def main_page():
    global log_ui
    """
    Root page definition
    """
    dark = ui.dark_mode(CastAPI.dark_mode).bind_value_to(CastAPI, 'dark_mode')

    apply_custom()

    if str2bool(cfg_mgr.custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)

    """
    timer created on main page run to refresh datas
    """
    ui.timer(int(cfg_mgr.app_config['timer']), callback=root_timer_action)

    """
    Header with button menu
    """
    await nice.head_set(name='Main', target='/', icon='home')

    """
    App info
    """
    if str2bool(cfg_mgr.custom_config['animate-ui']):
        head_row_anim = Animate(ui.row, animation_name_in='backInDown', duration=1)
        head_row = head_row_anim.create_element()
    else:
        head_row = ui.row()

    with head_row.classes('w-full no-wrap'):
        ui.label('DESKTOP: Cast Screen / Window content').classes('bg-slate-400 w-1/3')
        with ui.card().classes('bg-slate-400 w-1/3'):
            img = ui.image("assets/favicon.ico").classes('self-center')
            img.on('click', lambda: animate_toggle(img))
            img.style('cursor: pointer')
            img.tailwind.border_width('4').width('8')
        ui.label('MEDIA: Cast Image / Video / Capture Device (e.g. USB Camera ...)').classes('bg-slate-400 w-1/3')

    """
    WLEDVideoSync image
    """

    ui.separator().classes('mt-6')
    CastAPI.w_image = ui.image("assets/Source-intro.png").classes('self-center')
    CastAPI.w_image.classes(add='animate__animated')
    CastAPI.w_image.tailwind.border_width('8').width('1/6')

    """
    Video player
    """
    if str2bool(cfg_mgr.custom_config['player']):
        await video_player_page()
        CastAPI.player.set_visibility(False)

    """
    Row for Cast /Filters / info / Run / Close 
    """
    # filters for Desktop / Media
    with ui.row().classes('self-center'):

        await nice.filters_data(Desktop)

        with ui.card().tight().classes('w-42'):
            with ui.column():

                # refreshable
                await cast_manage_page()
                # end refreshable

                ui.icon('info') \
                    .tooltip('Show details') \
                    .on('click', lambda: show_thread_info()) \
                    .classes('self-center') \
                    .style('cursor: pointer')
                with ui.row().classes('self-center'):
                    with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700'):
                        with ui.row():
                            ui.checkbox('') \
                                .bind_value(Desktop, 'preview_top', forward=lambda value: value) \
                                .tooltip('Preview always on TOP').classes('w-10')
                            ui.knob(640, min=8, max=1920, step=1, show_value=True) \
                                .bind_value(Desktop, 'preview_w') \
                                .tooltip('Preview size W').classes('w-10')
                            ui.knob(360, min=8, max=1080, step=1, show_value=True) \
                                .bind_value(Desktop, 'preview_h') \
                                .tooltip('Preview size H').classes('w-10')
                    with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700'):
                        with ui.row():
                            ui.knob(640, min=8, max=1920, step=1, show_value=True) \
                                .bind_value(Media, 'preview_w') \
                                .tooltip('Preview size W').classes('w-10')
                            ui.knob(360, min=8, max=1080, step=1, show_value=True) \
                                .bind_value(Media, 'preview_h') \
                                .tooltip('Preview size H').classes('w-10')
                            ui.checkbox('') \
                                .bind_value(Media, 'preview_top', forward=lambda value: value) \
                                .tooltip('Preview always on TOP').classes('w-10')

                # presets
                with ui.row().classes('self-center'):

                    manage_filter_presets('Desktop')
                    manage_filter_presets('Media')

                # refreshable
                with ui.expansion('Monitor', icon='query_stats').classes('self-center w-full'):
                    if str2bool(cfg_mgr.custom_config['system-stats']):
                        with ui.row().classes('self-center'):
                            frame_count = ui.number(prefix='F:').bind_value_from(CastAPI, 'total_frame')
                            frame_count.tooltip('TOTAL Frames')
                            frame_count.classes("w-20")
                            frame_count.props(remove='type=number', add='borderless')

                            total_reset_icon = ui.icon('restore')
                            total_reset_icon.style("cursor: pointer")
                            total_reset_icon.on('click', lambda: reset_total())

                            packet_count = ui.number(prefix='P:').bind_value_from(CastAPI, 'total_packet')
                            packet_count.tooltip('TOTAL DDP Packets')
                            packet_count.classes("w-25")
                            packet_count.props(remove='type=number', add='borderless')

                        ui.separator()

                        with ui.row().classes('self-center'):
                            cpu_count = ui.number(prefix='CPU%: ').bind_value_from(CastAPI, 'cpu')
                            cpu_count.classes("w-20")
                            cpu_count.props(remove='type=number', add='borderless')

                            ram_count = ui.number(prefix='RAM%: ').bind_value_from(CastAPI, 'ram')
                            ram_count.classes("w-20")
                            ram_count.props(remove='type=number', add='borderless')

                    if str2bool(cfg_mgr.custom_config['cpu-chart']):
                        await nice.create_cpu_chart(CastAPI)

        await nice.filters_data(Media)

    ui.separator().classes('mt-6')

    """
    Log display
    """

    if str2bool(cfg_mgr.app_config['log_to_main']):
        with ui.expansion('Show log', icon='feed').classes('w-full'):
            log_ui = ui.log(max_lines=250).classes('w-full h-30 bg-black text-white')
            # logging Level
            cfg_mgr.logger.setLevel(cfg_mgr.app_config['log_level'].upper())
            # handler
            handler = LogElementHandler(log_ui)
            cfg_mgr.logger.addHandler(handler)
            ui.context.client.on_disconnect(lambda: cfg_mgr.logger.removeHandler(handler))
            # clear / load log file
            with ui.row().classes('w-full'):
                ui.button('Clear Log', on_click=lambda: log_ui.clear()).tooltip('Erase the log')
                dialog = ui.dialog().classes('w-full') \
                    .props(add='maximized transition-show="slide-up" transition-hide="slide-down"')
                with (dialog, ui.card().classes('w-full')):
                    log_filename = cfg_mgr.app_root_path('log/WLEDVideoSync.log')
                    if PathLib(log_filename).is_file():
                        # file exists
                        log_data = PathLib(log_filename).read_text()
                    else:
                        log_data = 'ERROR Log File Not Found ERROR'
                        cfg_mgr.logger.error(f'Log File Not Found {log_filename}')
                    ui.button('Close', on_click=dialog.close, color='red')
                    log_area = ui.textarea(value=log_data).classes('w-full').props(add='bg-color=blue-grey-4')
                    log_area.props(add="rows='25'")
                ui.button('See Log file', on_click=dialog.open).tooltip('Load log data from file.')

    """
    Footer : usefully links help
    """
    with ui.footer(value=False).classes('items-center bg-red-900') as footer:
        ui.switch("Light/Dark Mode", on_change=dark.toggle).classes('bg-red-900').tooltip('Change Layout Mode')

        await net_view_page()

        ui.button('Run discovery', on_click=discovery_net_notify, color='bg-red-800')
        ui.button('SysStats', on_click=charts_select, color='bg-red-800')
        CastAPI.charts_row = ui.row().classes('w-full no-wrap')
        with CastAPI.charts_row:
            with ui.card().classes('w-1/3'):
                ui.button('Device', on_click=dev_stats_info_page)

            with ui.card().classes('w-1/3'):
                ui.button('Network', on_click=net_stats_info_page)

            with ui.card().classes('w-1/3'):
                ui.button('System', on_click=sys_stats_info_page)
        CastAPI.charts_row.set_visibility(False)
        ui.button('Fonts', on_click=font_select, color='bg-red-800')
        ui.button('PYEditor', on_click=lambda: ui.navigate.to('Pyeditor'), color='bg-red-800')
        if sys.platform.lower() != 'win32':
            ui.button('shutdown', on_click=app.shutdown)
        with ui.row().classes('absolute inset-y-0 right-0.5 bg-red-900'):
            ui.link('® Zak-45 ' + str(datetime.now().strftime('%Y')), 'https://github.com/zak-45', new_tab=True) \
                .classes('text-white')
            ui.link('On-Line Help', 'https://github.com/zak-45/WLEDVideoSync?tab=readme-ov-file#user-guide', new_tab=True) \
                .tooltip('Go to documentation').classes('text-white')

    with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
        with ui.button(on_click=footer.toggle).props(add='round outline'):
            ui.image('assets/favicon.ico').classes('rounded-full w-8 h-8')


@ui.page('/Manage')
async def main_page_cast_manage():
    """ Cast manage with full details page """

    ui.dark_mode(CastAPI.dark_mode)

    apply_custom()

    """
    Header with button menu
    """
    await nice.head_set(name='Manage', target='/Manage', icon='video_settings')

    """
    Main tabs infos
    """
    await tabs_info_page()

    """
    Footer
    """
    with ui.footer():
        await net_view_page()

        await media_dev_view_page()


@ui.page('/Player')
async def run_video_player_page():
    """
    timer created on video creation to refresh datas
    """
    if str2bool(cfg_mgr.custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)
    ui.timer(int(cfg_mgr.app_config['timer']), callback=player_timer_action)
    await video_player_page()


async def video_player_page():
    """
    Video player
    """
    if str2bool(cfg_mgr.custom_config['animate-ui']):
        center_card_anim = Animate(ui.card, animation_name_in='fadeInUp', duration=1)
        center_card = center_card_anim.create_element()
    else:
        center_card = ui.card()

    center_card.classes('self-center w-2/3 bg-gray-500')
    with center_card:

        CastAPI.player = ui.video(cfg_mgr.app_root_path(cfg_mgr.app_config["video_file"])).classes('self-center')
        CastAPI.player.on('ended', lambda _: ui.notify('Video playback completed.'))
        CastAPI.player.on('timeupdate', lambda: get_player_time())
        CastAPI.player.on('durationchange', lambda: player_duration())
        CastAPI.player.set_visibility(True)

        with ui.row(wrap=False).classes('self-center'):
            ui.label() \
                .bind_text_from(Media, 'sync_to_time') \
                .classes('self-center bg-slate-400') \
                .bind_visibility_from(CastAPI.player)
            ui.label('+').bind_visibility_from(CastAPI.player)
            ui.label() \
                .bind_text_from(Media, 'add_all_sync_delay') \
                .classes('self-center bg-slate-400') \
                .bind_visibility_from(CastAPI.player)
        CastAPI.video_slider = ui.slider(min=0, max=7200, step=1, value=0,
                                         on_change=lambda var: slider_time(var.value)).props('label-always') \
            .bind_visibility_from(CastAPI.player)

        with ui.row().classes('self-center'):
            media_frame = ui.knob(0, min=-1000, max=1000, step=1, show_value=True).classes('bg-gray')
            media_frame.bind_value(Media, 'cast_skip_frames')
            media_frame.tooltip('+ / - frames to CAST')
            media_frame.bind_visibility_from(CastAPI.player)

            CastAPI.media_button_sync = ui.button('VSync', on_click=player_sync, color='green') \
                .tooltip('Sync Cast with Video Player Time') \
                .bind_visibility_from(CastAPI.player)

            media_reset_icon = ui.icon('restore')
            media_reset_icon.tooltip('sync Reset')
            media_reset_icon.style("cursor: pointer")
            media_reset_icon.on('click', lambda: reset_sync())
            media_reset_icon.bind_visibility_from(CastAPI.player)

            """ Refreshable """
            nice.sync_button(CastAPI, Media)
            """ End Refresh """

            CastAPI.slider_button_sync = ui.button('TSync', on_click=slider_sync, color='green') \
                .tooltip('Sync Cast with Slider Time') \
                .bind_visibility_from(CastAPI.player)

            media_sync_delay = ui.knob(1, min=1, max=59, step=1, show_value=True).classes('bg-gray')
            media_sync_delay.bind_value(Media, 'auto_sync_delay')
            media_sync_delay.tooltip('Interval in sec to auto sync')
            media_sync_delay.bind_visibility_from(CastAPI.player)

            media_auto_sync = ui.checkbox('Auto Sync') \
                .bind_value(Media, 'auto_sync') \
                .tooltip('Auto Sync Cast with Time every x sec (based on interval set)') \
                .bind_visibility_from(CastAPI.player)

            media_all_sync_delay = ui.knob(1, min=-2000, max=2000, step=1, show_value=True).classes('bg-gray') \
                .bind_value(Media, 'add_all_sync_delay') \
                .tooltip('Add Delay in ms to all sync') \
                .bind_visibility_from(CastAPI.player)

            media_all_sync = ui.checkbox('Sync All') \
                .bind_value(Media, 'all_sync') \
                .tooltip('Sync All Casts with selected time') \
                .bind_visibility_from(CastAPI.player)

        with ui.row().classes('self-center'):
            ui.icon('switch_video', color='blue', size='md') \
                .style("cursor: pointer") \
                .on('click', lambda visible=True: (CastAPI.player.set_visibility(visible),
                                                   nice.animate_wled_image(CastAPI, visible))) \
                .tooltip("Show Video player")

            hide_player = ui.icon('cancel_presentation', color='red', size='md') \
                .style("cursor: pointer") \
                .on('click', lambda visible=False: (CastAPI.player.set_visibility(visible),
                                                    nice.animate_wled_image(CastAPI, visible))) \
                .tooltip("Hide Video player")

            cast_player = ui.icon('cast', size='md') \
                .style("cursor: pointer") \
                .on('click', lambda: player_cast(CastAPI.player.source)) \
                .tooltip('Play/Cast Video') \
                .bind_visibility_from(CastAPI.player)

            cast_number = ui.number(min=-1, max=9999, precision=0, placeholder='Repeat')
            cast_number.tooltip('Enter number of time you want to re-cast Media')
            cast_number.bind_value(Media, 'repeat')
            cast_number.bind_visibility_from(CastAPI.player)

            media_info = ui.icon('info', size='sd') \
                .style("cursor: pointer") \
                .on('click', lambda: nice.player_media_info(CastAPI.player.source)) \
                .tooltip('Media Info') \
                .bind_visibility_from(CastAPI.player)

            video_file = ui.icon('folder', color='orange', size='md') \
                .style("cursor: pointer") \
                .on('click', lambda: nice.player_pick_file(CastAPI)) \
                .tooltip('Select audio / video file') \
                .bind_visibility_from(CastAPI.player)

            video_img_url = ui.input('Enter video/image Url / Path', placeholder='http://....') \
                .bind_visibility_from(CastAPI.player)
            video_img_url.tooltip('Enter Url, click on icon to download video/image, '
                                  ' hide and show player should refresh data')
            video_img_url.on('focus', js_handler='''(event) => {const input = event.target;input.select();}''')
            video_url_icon = ui.icon('published_with_changes')
            video_url_icon.style("cursor: pointer")
            video_url_icon.tooltip("Download video/image from Url")
            video_url_icon.on('click', lambda: download_url(video_img_url.value))
            video_url_icon.bind_visibility_from(CastAPI.player)

            # if yt-enable is True display YT info icon
            if str2bool(cfg_mgr.custom_config['yt-enable']):
                video_url_info = ui.icon('info')
                video_url_info.style("cursor: pointer")
                video_url_info.tooltip("Youtube/Url information's, including formats etc ...")
                video_url_info.on('click', lambda: nice.player_url_info(video_img_url.value))
                video_url_info.bind_visibility_from(CastAPI.player)

            # Progress bar
            CastAPI.progress_bar = ui.linear_progress(value=0, show_value=False, size='8px')

        # if yt-enable is True display YT search buttons
        if str2bool(cfg_mgr.custom_config['yt-enable']):
            with ui.row(wrap=True).classes('w-full'):
                # YT search
                yt_icon = ui.chip('YT Search',
                                  icon='youtube_searched_for',
                                  color='indigo-3',
                                  on_click=lambda: youtube_search())
                yt_icon.classes('fade')
                yt_icon.bind_visibility_from(CastAPI.player)
                yt_icon = ui.chip('Clear YT Search',
                                  icon='clear',
                                  color='indigo-3',
                                  on_click=lambda: youtube_clear_search())
                yt_icon.bind_visibility_from(CastAPI.player)


@ui.page('/Desktop')
async def main_page_desktop():
    """
    Desktop param page
    """
    ui.dark_mode(CastAPI.dark_mode)

    apply_custom()

    await nice.head_set(name='Desktop Params', target='/Desktop', icon='computer')

    if str2bool(cfg_mgr.custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)

    columns_a = [
        {'name': 'rate', 'label': 'FPS', 'field': 'rate', 'align': 'left'},
        {'name': 'scale_width', 'label': 'W', 'field': 'scale_width'},
        {'name': 'scale_height', 'label': 'H', 'field': 'scale_height'}
    ]
    rows_a = [
        {'id': 0, 'rate': Desktop.rate, 'scale_width': Desktop.scale_width, 'scale_height': Desktop.scale_height}
    ]
    columns_b = [
        {'name': 'wled', 'label': 'WLED', 'field': 'wled', 'align': 'left'},
        {'name': 'host', 'label': 'IP', 'field': 'host'}
    ]
    rows_b = [
        {'id': 0, 'wled': Desktop.wled, 'host': Desktop.host}
    ]
    columns_c = [
        {'name': 'viinput', 'label': 'Input', 'field': 'viinput', 'align': 'left'},
        {'name': 'viformat', 'label': 'Method', 'field': 'viformat'},
        {'name': 'preview', 'label': 'Preview', 'field': 'preview'}
    ]
    rows_c = [
        {'id': 0, 'viinput': Desktop.viinput, 'viformat': Desktop.viformat, 'preview': Desktop.preview}
    ]
    columns_d = [
        {'name': 'vooutput', 'label': 'Output', 'field': 'vooutput', 'align': 'left'},
        {'name': 'voformat', 'label': 'Format', 'field': 'voformat'},
        {'name': 'vo_code', 'label': 'Codec', 'field': 'vo_codec'}
    ]
    rows_d = [
        {'id': 0, 'vooutput': Desktop.vooutput, 'voformat': Desktop.voformat, 'vo_codec': Desktop.vo_codec}
    ]

    columns_e = [
        {'name': 'multicast', 'label': 'MultiCast', 'field': 'multicast', 'align': 'left'},
        {'name': 'matrix-x', 'label': 'H', 'field': 'matrix-x'},
        {'name': 'matrix-y', 'label': 'V', 'field': 'matrix-y'}
    ]
    rows_e = [
        {'id': 0, 'multicast': Desktop.multicast, 'matrix-x': Desktop.cast_x, 'matrix-y': Desktop.cast_y}
    ]

    exp_param = ui.expansion('Parameters', icon='settings', value=True)
    with exp_param.classes('w-full bg-sky-800'):

        with ui.row():
            await nice.cast_icon(Desktop)
            manage_cast_presets('Desktop')

        with ui.row():
            ui.table(columns=columns_a, rows=rows_a).classes('w-60')
            ui.table(columns=columns_b, rows=rows_b).classes('w-60')
            ui.table(columns=columns_c, rows=rows_c).classes('w-60')
            ui.table(columns=columns_d, rows=rows_d).classes('w-60')
            ui.table(columns=columns_e, rows=rows_e).classes('w-60')

            with ui.grid(columns=2):
                ui.label('Protocol:')
                ui.label(Desktop.protocol)

                ui.label('Port:')
                ui.label(str(Desktop.port))

                ui.label('No of Packet:')
                ui.label(str(Desktop.retry_number))

    if str2bool(cfg_mgr.custom_config['animate-ui']):
        exp_edit_param_anim = Animate(ui.expansion, animation_name_in='backInDown', duration=1)
        exp_edit_param = exp_edit_param_anim.create_element()
    else:
        exp_edit_param = ui.expansion()

    exp_edit_param.text = 'Edit'
    exp_edit_param.props(add="icon='edit'")
    exp_edit_param.classes('w-full bg-sky-800')
    exp_edit_param.on_value_change(lambda: exp_param.close())

    with exp_edit_param:
        with ui.row():
            ui.icon('restore_page', color='blue', size='md') \
                .style('cursor: pointer').tooltip('Click to Validate/Refresh') \
                .on('click', lambda: ui.navigate.to('/Desktop'))

            with ui.card():
                await nice.edit_rate_x_y(Desktop)

            with ui.card():
                new_wled = ui.checkbox('wled')
                new_wled.bind_value(Desktop, 'wled')
                new_wled.tooltip('Is That a WLED Device ?')
                new_host = ui.input('IP', value=Desktop.host)
                new_host.tooltip('IP address of the device')
                new_host.on('focusout', lambda: update_attribute_by_name('Desktop', 'host', new_host.value))


            with ui.card():
                input_options=['area','win=','queue']
                if sys.platform.lower() == 'win32':
                    input_options.insert(0,'desktop')
                elif sys.platform.lower() == 'linux':
                    input_options.insert(0,os.getenv('DISPLAY'))
                new_viinput = ui.select(options=input_options,label='Input', new_value_mode='add-unique')
                new_viinput.tooltip('Type data to capture, "area" for screen selection, "win=xxxxx" for win title You will need to press ENTER Key')
                new_viinput.on('focusout', lambda: update_attribute_by_name('Desktop', 'viinput', str(new_viinput.value)))
                new_preview = ui.checkbox('Preview')
                new_preview.bind_value(Desktop, 'preview')
                new_preview.tooltip('Show preview window')
                new_viformat = ui.input('Format', value=Desktop.viformat)
                new_viformat.bind_value(Desktop, 'viformat')
                new_vi_codec = ui.input('Codec', value=Desktop.vi_codec)
                new_vi_codec.bind_value(Desktop, 'vi_codec')
                with ui.row():
                    ui.number('', value=Desktop.monitor_number, min=0, max=1).classes('w-10') \
                        .bind_value(Desktop, 'monitor_number', forward=lambda value: int(value or 0)) \
                        .tooltip('Enter monitor number')
                    ui.button('ScreenArea', on_click=select_sc_area) \
                        .tooltip('Select area from monitor')

            with ui.card():
                new_vooutput = ui.input('Output', value=str(Desktop.vooutput))
                new_vooutput.bind_value(Desktop, 'vooutput')
                new_vooutput.tooltip('Experimental feature: enter udp:// rtsp:// etc...')
                new_voformat = ui.input('Format', value=Desktop.voformat)
                new_voformat.bind_value(Desktop, 'voformat')
                ui.button('formats', on_click=nice.display_formats)
                new_vo_codec = ui.input('Codec', value=Desktop.vo_codec)
                new_vo_codec.bind_value(Desktop, 'vo_codec')
                ui.button('Codecs', on_click=nice.display_codecs)

            with ui.card():

                await nice.edit_capture(Desktop)

            with ui.card():

                await nice.edit_multicast(Desktop)

            with ui.card():
                new_cast_devices = ui.input('Cast Devices', value=str(Desktop.cast_devices))
                new_cast_devices.tooltip('Click on MANAGE to enter devices for Multicast')
                new_cast_devices.on('focusout',
                                    lambda: update_attribute_by_name('Desktop', 'cast_devices', new_cast_devices.value))
                ui.button('Manage', on_click=lambda: nice.cast_device_manage(Desktop, Netdevice))

            with ui.card():
                await nice.edit_protocol(Desktop)

            with ui.card():
                await nice.edit_artnet(Desktop)

            with ui.card():
                new_record = ui.checkbox(text='Record', value=False).bind_value(Desktop,'record')
                new_record.tooltip('Select if want to record cast')
                new_record_file = ui.input('File name').bind_value(Desktop,'output_file')
                new_record_file.tooltip('Provide file name for record, extension determine format eg: file.mp4')

    ui.separator().classes('mt-6')

    with ui.expansion('BUFFER', icon='grid_view', on_value_change=lambda: exp_edit_param.close()) \
            .classes('w-full'):
        if len(Desktop.frame_buffer) > 0:
            with ui.row():
                media_grid = ui.grid(columns=8)
                with media_grid:
                    for i in range(len(Desktop.frame_buffer)):
                        # put fixed size for preview
                        img = CV2Utils.resize_image(Desktop.frame_buffer[i], 640, 360)
                        img = Image.fromarray(img)
                        await light_box_image(i, img, '', '', Desktop, 'frame_buffer')
                with ui.carousel(animated=True, arrows=True, navigation=True).props('height=480px'):
                    await nice.generate_carousel(Desktop)

        else:
            with ui.card():
                ui.label('No image to show...').classes('animate-pulse')

    with ui.expansion('MULTICAST', icon='grid_view', on_value_change=lambda: exp_edit_param.close()) \
            .classes('w-full'):
        # columns number  = cast_x, number of cards = cast_x * cast_y
        if Desktop.multicast:
            with ui.row():
                await nice.multi_preview(Desktop)
                await nice.cast_devices_view(Desktop)
            if len(Desktop.cast_frame_buffer) > 0:
                with ui.grid(columns=Desktop.cast_x):
                    try:
                        for i in range(Desktop.cast_x * Desktop.cast_y):
                            # put fixed size for preview
                            img = CV2Utils.resize_image(Desktop.cast_frame_buffer[i], 640, 360)
                            img = Image.fromarray(img)
                            await light_box_image(i, img, i, '', Desktop, 'cast_frame_buffer')
                    except Exception as m_error:
                        cfg_mgr.logger.error(traceback.format_exc())
                        cfg_mgr.logger.error(f'An exception occurred: {m_error}')
            else:
                with ui.card():
                    ui.label('No frame captured yet...').style('background: red')
        else:
            with ui.card():
                ui.label('Multicast not set') \
                    .style('text-align:center; font-size: 150%; font-weight: 300') \
                    .classes('animate-pulse')

    with ui.footer():

        await net_view_page()

        async def display_windows():
            with ui.dialog() as dialog, ui.card():
                dialog.open()
                editor = ui.json_editor({'content': {'json': Desktop.windows_titles}}) \
                    .run_editor_method('updateProps', {'readOnly': False})
                ui.button('Close', on_click=dialog.close, color='red')

        ui.button('Win TITLES', on_click=display_windows, color='bg-red-800').tooltip('View windows titles')
        ui.button('Fetch Win TITLES', on_click=grab_windows, color='bg-red-800').tooltip('Retrieve windows titles')


@ui.page('/Media')
async def main_page_media():
    """
    Media param page
    """
    ui.dark_mode(CastAPI.dark_mode)

    apply_custom()

    await nice.head_set(name='Media Params', target='/Media', icon='image')

    if str2bool(cfg_mgr.custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)

    columns_a = [
        {'name': 'rate', 'label': 'FPS', 'field': 'rate', 'align': 'left'},
        {'name': 'scale_width', 'label': 'W', 'field': 'scale_width'},
        {'name': 'scale_height', 'label': 'H', 'field': 'scale_height'}
    ]
    rows_a = [
        {'id': 0, 'rate': Media.rate, 'scale_width': Media.scale_width, 'scale_height': Media.scale_height}
    ]
    columns_b = [
        {'name': 'wled', 'label': 'WLED', 'field': 'wled', 'align': 'left'},
        {'name': 'host', 'label': 'IP', 'field': 'host'}
    ]
    rows_b = [
        {'id': 0, 'wled': Media.wled, 'host': Media.host}
    ]
    columns_c = [
        {'name': 'viinput', 'label': 'Input', 'field': 'viinput', 'align': 'left'},
        {'name': 'preview', 'label': 'Preview', 'field': 'preview'}
    ]
    rows_c = [
        {'id': 0, 'viinput': Media.viinput, 'preview': Media.preview}
    ]
    columns_d = [
        {'name': 'multicast', 'label': 'MultiCast', 'field': 'multicast', 'align': 'left'},
        {'name': 'matrix-x', 'label': 'H', 'field': 'matrix-x'},
        {'name': 'matrix-y', 'label': 'V', 'field': 'matrix-y'}
    ]
    rows_d = [
        {'id': 0, 'multicast': Media.multicast, 'matrix-x': Media.cast_x, 'matrix-y': Media.cast_y}
    ]
    media_exp_param = ui.expansion('Parameters', icon='settings', value=True)
    with media_exp_param.classes('w-full bg-sky-800'):

        with ui.row(wrap=False):
            await nice.cast_icon(Media)
            manage_cast_presets('Media')

        with ui.row():
            ui.table(columns=columns_a, rows=rows_a).classes('w-60')
            ui.table(columns=columns_b, rows=rows_b).classes('w-60')
            ui.table(columns=columns_c, rows=rows_c).classes('w-60')
            ui.table(columns=columns_d, rows=rows_d).classes('w-60')

            with ui.grid(columns=2):
                ui.label('Protocol:')
                ui.label(Media.protocol)

                ui.label('Port:')
                ui.label(str(Media.port))

                ui.label('No of Packet:')
                ui.label(str(Media.retry_number))

    if str2bool(cfg_mgr.custom_config['animate-ui']):
        media_exp_edit_param_anim = Animate(ui.expansion, animation_name_in='backInDown', duration=1)
        media_exp_edit_param = media_exp_edit_param_anim.create_element()
    else:
        media_exp_edit_param = ui.expansion()

    media_exp_edit_param.text = 'Edit'
    media_exp_edit_param.props(add="icon='edit'")
    media_exp_edit_param.classes('w-full bg-sky-800')
    media_exp_edit_param.on_value_change(lambda: media_exp_param.close())

    with media_exp_edit_param:
        with ui.row():
            ui.icon('restore_page', color='blue', size='md') \
                .style('cursor: pointer').tooltip('Click to Validate/Refresh') \
                .on('click', lambda: ui.navigate.to('/Media'))

            with ui.card():
                await nice.edit_rate_x_y(Media)

            with ui.card():
                new_viinput = ui.input('Input', value=str(Media.viinput))
                new_viinput.on('focusout', lambda: update_attribute_by_name('Media', 'viinput', new_viinput.value))
                new_viinput.tooltip('Enter desired input : e.g 0..n / file name  etc ...')
                new_preview = ui.checkbox('Preview')
                new_preview.bind_value(Media, 'preview')
                new_preview.tooltip('Show preview window')

            with ui.card():
                new_wled = ui.checkbox('wled')
                new_wled.bind_value(Media, 'wled')
                new_wled.tooltip('Is That a WLED Device ?')
                new_host = ui.input('IP', value=Media.host)
                new_host.tooltip('IP address of the device')
                new_host.on('focusout', lambda: update_attribute_by_name('Media', 'host', new_host.value))

            with ui.card():

                await nice.edit_capture(Media)

            with ui.card():

                await nice.edit_multicast(Media)

            with ui.card():

                await nice.edit_protocol(Media)

            with ui.card():

                await nice.edit_artnet(Media)

            with ui.card():
                new_cast_devices = ui.input('Cast Devices', value=str(Media.cast_devices))
                new_cast_devices.tooltip('Click on MANAGE to enter devices for Multicast')
                new_cast_devices.on('focusout',
                                    lambda: update_attribute_by_name('Media', 'cast_devices', new_cast_devices.value))
                ui.button('Manage', on_click=lambda: nice.cast_device_manage(Media, Netdevice))

    ui.separator().classes('mt-6')

    with ui.expansion('BUFFER', icon='grid_view', on_value_change=lambda: media_exp_edit_param.close()) \
            .classes('w-full'):
        if len(Media.frame_buffer) > 0:
            with ui.row():
                media_grid = ui.grid(columns=8)
                with media_grid:
                    for i in range(len(Media.frame_buffer)):
                        # put fixed size for preview
                        img = CV2Utils.resize_image(Media.frame_buffer[i], 640, 360)
                        img = Image.fromarray(img)
                        await light_box_image(i, img, '', '', Media, 'frame_buffer')
                with ui.carousel(animated=True, arrows=True, navigation=True).props('height=480px'):
                    await nice.generate_carousel(Media)

        else:
            with ui.card():
                ui.label('No image to show...').classes('animate-pulse')

    with ui.expansion('MULTICAST', icon='grid_view', on_value_change=lambda: media_exp_edit_param.close()) \
            .classes('w-full'):
        # columns number  = cast_x, number of cards = cast_x * cast_y
        if Media.multicast:
            with ui.row():
                await nice.multi_preview(Media)
                await nice.cast_devices_view(Media)
            if len(Media.cast_frame_buffer) > 0:
                with ui.grid(columns=Media.cast_x):
                    try:
                        for i in range(Media.cast_x * Media.cast_y):
                            # put fixed size for preview
                            img = CV2Utils.resize_image(Media.cast_frame_buffer[i], 640, 360)
                            img = Image.fromarray(img)
                            await light_box_image(i, img, i, '', Media, 'cast_frame_buffer')
                    except Exception as e:
                        cfg_mgr.logger.error(traceback.format_exc())
                        cfg_mgr.logger.error(f'An exception occurred: {e}')
            else:
                with ui.card():
                    ui.label('No frame captured yet...').style('background: red')
        else:
            with ui.card():
                ui.label('Multicast not set') \
                    .style('text-align:center; font-size: 150%; font-weight: 300') \
                    .classes('animate-pulse')

    ui.separator().classes('mt-6')

    with ui.footer():

        await net_view_page()

        await media_dev_view_page()

        ui.button('Run discovery', on_click=discovery_media_notify, color='bg-red-800')


@ui.page('/WLEDVideoSync')
async def splash_page():
    """
    Page displayed on the webview window
    :return:
    """
    ui.dark_mode(True)
    ui.image('media/intro.gif').classes('self-center').style('width: 50%')
    main = ui.button(
        'MAIN INTERFACE',
        on_click=lambda: (main.props('loading'), ui.navigate.to('/')),
    ).classes('self-center')
    ui.button('API', on_click=lambda: ui.navigate.to('/docs')).classes(
        'self-center'
    )


@ui.page('/ws/docs')
async def ws_page():
    """
    websocket docs page
    :return:
    """
    ui.label('WEBSOCKETS Doc').classes('self-center')
    doc_txt = ui.textarea('WE endpoints').style('width: 50%')
    doc_txt.value = ( '/ws: e.g: ws://localhost:8000/ws \n'
                      '/ws/docs: e.g: http://localhost:8000/ws/docs \n'
                      'communication type : Json for in/out \n'
                      'format : {"action":{"type":"xxx","param":{"yyy":"zzz"...}}} \n'
                      'example: \n'
                     '{"action":'
                     '{"type":"cast_image", '
                     '"param":{"image_number":0,"device_number":-1, "class_name":"Media"}}}'
                     )

    ws_modules=['Utils','Net','ImageUtils','CV2Utils']
    func_rows = ui.row()

    def fetch_main_module():
        with ui.dialog() as dialog_m, ui.card():
            dialog_m.open()
            ui.json_editor({'content': {'json': Utils.func_info(sys.modules[__name__])}}) \
                .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog_m.close, color='red')

    def fetch_all_modules():
        with ui.dialog() as dialog_a, ui.card():
            dialog_a.open()
            ui.json_editor({'content': {'json': Utils.func_info(globals()[item_th])}}) \
                    .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog_a.close, color='red')

    with func_rows:
        item_exp = ui.expansion('local', icon='info') \
            .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')
        with item_exp:
            ui.button('Functions', on_click=fetch_main_module, color='bg-red-800').tooltip('View func info')
        for item_th in ws_modules:
            item_exp = ui.expansion(item_th, icon='info') \
                .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')
            with item_exp:
                ui.button('Functions', on_click=fetch_all_modules, color='bg-red-800').tooltip('View func info')


@ui.page('/info')
async def info_page():
    """ simple cast info page from systray """
    if str2bool(cfg_mgr.custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)
    ui.timer(int(cfg_mgr.app_config['timer']), callback=info_timer_action)
    await cast_manage_page()


@ui.page('/DetailsInfo')
async def manage_info_page():
    """ Manage cast page from systray """
    await tabs_info_page()


@ui.page('/RunCharts')
async def manage_charts_page():
    """ Select chart """
    with ui.row(wrap=False).classes('w-full'):
        with ui.card().classes('w-1/3'):
            ui.button('Device', on_click=dev_stats_info_page)

        with ui.card().classes('w-1/3'):
            ui.button('Network', on_click=net_stats_info_page)

        with ui.card().classes('w-1/3'):
            ui.button('System', on_click=sys_stats_info_page)


@ui.page('/Fonts')
async def manage_font_page():

    ui.dark_mode(CastAPI.dark_mode)

    apply_custom()

    def selected_font(i_font_name):
        ui.notify(f'Selected font : {i_font_name}')

    # Search for all system fonts
    Utils.get_system_fonts()
    # update dict
    fonts = Utils.font_dict
    # init font class
    font_manager = FontPreviewManager(fonts)

    with ui.column().classes('p-4 h-full w-full') as layout:

        async def filter_fonts(e):
            query = e.value.lower()
            font_list.clear()
            matching_fonts = font_manager.filter_fonts(query) # Use the class method
            for list_font_name in matching_fonts:
                with font_list:
                    font_label = ui.label(list_font_name).classes("cursor-pointer hover:underline")
                    font_label.on(
                        "mouseover",
                        lambda z=list_font_name, x=font_label: set_preview(fonts[z], x)
                    )
                    font_label.on(
                        "mouseout",
                        lambda x=font_label: x.classes(remove='bg-slate-300')
                    )
                    font_label.on(
                        "click",
                        lambda x=font_label: selected_font(x.text)
                    )

        async def set_preview(font_path, font_label):
            font_label.classes(add='bg-slate-300')
            if preview_data := font_manager.get_preview(font_path, font_label): # Use class method, get preview data
                preview_image.set_source(preview_data) # Set preview image source

        ui.label("Hover over a font to see a preview").classes("text-sm font-bold mb-4")

        # Search bar
        search_input = ui.input(
            label="Search Fonts",
            placeholder="Type to search...",
            on_change=filter_fonts,
        ).classes("mb-4 w-full")

        # Searchable font list
        font_list = ui.column().classes(
            'w-full flex-grow overflow-y-auto border rounded shadow p-2 max-h-[40vh]')

        font_name = ui.label('Font name :')
        font_name.classes('self-center')
        font_name.bind_text_from(font_manager,'selected_font_label',
                                 backward=lambda v: font_manager.selected_font_label.text)

        # image preview of font
        preview_image = ui.image().classes("border rounded shadow mb-4").style(
            "width: 100%; height: 100px; background-color: white;")

        # slider for font size preview
        s_font_size = ui.slider(min=1, max=100, value=25,
                                on_change=lambda var: set_preview(font_manager.selected_font_path,
                                                                  font_manager.selected_font_label))

        s_font_size.bind_value_to(font_manager,'font_size')


    # Populate font list initially
    search_input.set_value("")
    await filter_fonts(search_input) # Call filter_fonts to populate the list initially

@ui.page('/Coldtype')
async def coldtype_test_page():

    ui.dark_mode(CastAPI.dark_mode)

    apply_custom()

    def cold_run():
        cold = RUNColdtype()
        cold.start()

    ui.button('run Coldtype', on_click=cold_run).classes('self-cnter')

    print('end of coldtype page load')


@ui.page('/Pyeditor')
async def pyeditor_test_page():
    from src.utl.pyeditor import PythonEditor

    ui.dark_mode(CastAPI.dark_mode)

    apply_custom()

    # Instantiate and run the editor
    editor_app = PythonEditor()
    await editor_app.setup_ui()

    print('end of pyeditor page load')

"""
helpers /Commons
"""

async def grab_windows():
    """Retrieves and displays window titles.

    This function retrieves all window titles and displays a notification.
    """

    ui.notification('Retrieved all windows information', close_button=True, timeout=3)
    Desktop.windows_titles = Utils.windows_titles()


async def media_dev_view_page():
    """
    Display media devices into the Json Editor
    :return:
    """
    def fetch_dev():
        with ui.dialog() as dialog, ui.card():
            dialog.open()
            editor = ui.json_editor({'content': {'json': Utils.dev_list}}) \
                .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog.close, color='red')

    ui.button('Media devices', on_click=fetch_dev, color='bg-red-800').tooltip('View Media devices')


async def net_view_page():
    """
    Display network devices into the Json Editor
    :return:
    """
    def fetch_net():
        with ui.dialog() as dialog, ui.card():
            dialog.open()
            editor = ui.json_editor({'content': {'json': Netdevice.http_devices}}) \
                .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog.close, color='red')

    ui.button('Net devices', on_click=fetch_net, color='bg-red-800').tooltip('View network devices')

async def animate_toggle(img):
    """ toggle animation """

    if str2bool(cfg_mgr.custom_config['animate-ui']):
        # put animation False
        cfg_mgr.custom_config['animate-ui'] = 'False'
        img.classes('animate__animated animate__hinge')
    else:
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)
        # put animation True
        cfg_mgr.custom_config['animate-ui'] = 'True'
        img.classes('animate__animated animate__rubberBand')

    ui.notify(f'Animate :{cfg_mgr.custom_config["animate-ui"]}')
    cfg_mgr.logger.debug(f'Animate :{cfg_mgr.custom_config["animate-ui"]}')


async def youtube_search():
    """
    display search result from pytube
    """
    anime = False
    if str2bool(cfg_mgr.custom_config['animate-ui']):
        animated_yt_area = Animate(ui.scroll_area, animation_name_in="backInDown", duration=1.5)
        yt_area = animated_yt_area.create_element()
        anime = True
    else:
        yt_area = ui.scroll_area()

    yt_area.bind_visibility_from(CastAPI.player)
    yt_area.classes('w-full border')
    CastAPI.search_areas.append(yt_area)
    with yt_area:
        YtSearch(anime)


async def youtube_clear_search():
    """
    Clear search results
    """

    for area in CastAPI.search_areas:
        try:
            if str2bool(cfg_mgr.custom_config['animate-ui']):
                animated_area = Animate(area, animation_name_out="backOutUp", duration=1)
                animated_area.delete_element(area)
            else:
                area.delete()
        except Exception as y_error:
            cfg_mgr.logger.error(traceback.format_exc())
            cfg_mgr.logger.error(f'Search area does not exist: {y_error}')
    CastAPI.search_areas = []


async def reset_total():
    """ reset frames / packets total values for Media and Desktop """
    Media.reset_total = True
    Desktop.reset_total = True
    #  instruct first cast to reset values
    if len(Media.cast_names) != 0:
        result = action_to_thread(class_name='Media',
                                        cast_name=Media.cast_names[0],
                                        action='reset',
                                        clear=False,
                                        execute=True
                                        )
        ui.notify(result)

    if len(Desktop.cast_names) != 0:
        result = action_to_thread(class_name='Desktop',
                                        cast_name=Desktop.cast_names[0],
                                        action='reset',
                                        clear=False,
                                        execute=True
                                        )
        ui.notify(result)

    ui.notify('Reset Total')


async def select_sc_area():
    """ with mouse, draw rectangle to monitor x """

    monitor = int(Desktop.monitor_number)
    # run in no blocking way
    await run.io_bound(Sa.run, monitor)
    # For Calculate crop parameters
    Desktop.screen_coordinates = Sa.screen_coordinates
    #
    cfg_mgr.logger.debug(f'Monitor infos: {Sa.monitors}')
    cfg_mgr.logger.debug(f'Area Coordinates: {Sa.coordinates} from monitor {monitor}')
    cfg_mgr.logger.debug(f'Area screen Coordinates: {Sa.screen_coordinates} from monitor {monitor}')


async def player_sync():
    """ Set Sync cast to True """

    # client need to be connected
    await ui.context.client.connected()
    current_time = round(await ui.run_javascript("document.querySelector('video').currentTime", timeout=2))
    ui.notify(f'Player Time : {current_time}')
    # set time
    Media.sync_to_time = current_time * 1000
    Media.cast_sync = True
    CastAPI.type_sync = 'player'
    CastAPI.last_type_sync = 'player'
    # gui update
    CastAPI.media_button_sync.props(add="color=red")
    CastAPI.media_button_sync.text = current_time
    CastAPI.media_button_sync.classes('animate-pulse')
    CastAPI.slider_button_sync.props(remove="color=red")
    CastAPI.slider_button_sync.text = "TSYNC"


async def slider_sync():
    """ Set Sync Cast to True """

    current_time = CastAPI.video_slider.value
    ui.notify(f'Slider Time : {current_time}')
    # set time
    Media.sync_to_time = current_time * 1000
    Media.cast_sync = True
    CastAPI.type_sync = 'slider'
    CastAPI.last_type_sync = 'slider'
    # gui update
    CastAPI.slider_button_sync.props(add="color=red")
    CastAPI.slider_button_sync.text = current_time
    CastAPI.slider_button_sync.classes('animate-pulse')
    CastAPI.media_button_sync.props(remove="color=red")
    CastAPI.media_button_sync.text = "VSYNC"


def slider_time(current_time):
    """ Set player time for Cast """

    if CastAPI.type_sync == 'slider':
        Media.sync_to_time = current_time * 1000


def reset_sync():
    """ Reset player sync value to default """

    Media.cast_sync = False
    Media.auto_sync_delay = 30
    Media.add_all_sync_delay = 0
    ui.notify('Reset Sync')


async def get_player_time():
    """
    Retrieve current play time from the Player
    Set player time for Cast to Sync
    """
    await ui.context.client.connected()
    if CastAPI.type_sync == 'player':
        current_time = round(await ui.run_javascript("document.querySelector('video').currentTime", timeout=2))
        Media.sync_to_time = current_time * 1000


async def player_duration():
    """
    Return current duration time from the Player
    Set slider max value to video duration
    """
    await ui.context.client.connected()
    current_duration = await ui.run_javascript("document.querySelector('video').duration", timeout=2)
    ui.notify(f'Video duration:{current_duration}')
    Media.player_duration = current_duration
    CastAPI.video_slider._props["max"] = current_duration
    CastAPI.video_slider.update()


def charts_select():
    """
    select charts
    :return:
    """
    if os.path.isfile(select_chart_exe()):
        CastAPI.charts_row.set_visibility(True)
    else:
        ui.notify('No charts executable', type='warning')

async def font_select():
    """
    Font Page
    :return:
    """

    with ui.dialog() as font_dialog:
        font_dialog.open()
        with ui.card().classes('w-full'):
            await manage_font_page()
            ui.button('close', on_click=font_dialog.close).classes('self-center')


def dev_stats_info_page():
    """ devices charts """

    dev_ip = ['--dev_ip']
    ips_list = []
    if Desktop.host != '127.0.0.1':
        ips_list.append(Desktop.host)
    if Media.host != '127.0.0.1':
        ips_list.append(Media.host)

    ips_list.extend(
        Desktop.cast_devices[i][1] for i in range(len(Desktop.cast_devices))
    )
    ips_list.extend(
        Media.cast_devices[i][1] for i in range(len(Media.cast_devices))
    )
    
    if not ips_list:
        ips_list.append('127.0.0.1')

    ips_list = [','.join(ips_list)]

    dark = ['--dark'] if CastAPI.dark_mode is True else []
    # run chart on its own process
    Popen(["devstats"] + dev_ip + ips_list + dark,
          executable=select_chart_exe())

    cfg_mgr.logger.debug('Run Device(s) Charts')
    CastAPI.charts_row.set_visibility(False)


def net_stats_info_page():
    """ network charts """

    dark = ['--dark'] if CastAPI.dark_mode is True else []
    Popen(["netstats"] + dark,
          executable=select_chart_exe())

    CastAPI.charts_row.set_visibility(False)
    cfg_mgr.logger.debug('Run Network Chart')


def sys_stats_info_page():
    """ system charts """

    dark = ['--dark'] if CastAPI.dark_mode is True else []
    Popen(["sysstats"] + dark,
          executable=select_chart_exe())

    CastAPI.charts_row.set_visibility(False)
    cfg_mgr.logger.debug('Run System Charts')


def select_chart_exe():
    return cfg_mgr.app_config['charts_exe']


"""
Filter preset mgr
"""


def manage_filter_presets(class_name):
    """ Manage presets"""
    ui.button('save preset', on_click=lambda: save_filter_preset(class_name)).classes('w-20')
    ui.button('load preset', on_click=lambda: load_filter_preset(class_name)).classes('w-20')

async def save_filter_preset(class_name: str) -> None:
    """
    Save the current filter preset to an ini file.

    Parameters:
    - class_name (str): The name of the class to save the preset for. Must be 'Desktop' or 'Media'.
    """

    def save_file(f_name: str) -> None:
        if not f_name or not f_name.strip():
            ui.notify(f'Preset name could not be blank: {f_name}', type='negative')
            return

        f_name = cfg_mgr.app_root_path(f'config/presets/filter/{class_name}/{f_name}.ini')
        if os.path.isfile(f_name):
            ui.notify(f'Preset {f_name} already exists', type='warning')
            return

        try:
            class_obj = globals()[class_name]
            preset = configparser.ConfigParser()

            preset['RGB'] = {
                'balance_r': str(class_obj.balance_r),
                'balance_g': str(class_obj.balance_g),
                'balance_b': str(class_obj.balance_b)
            }
            preset['SCALE'] = {
                'scale_width': str(class_obj.scale_width),
                'scale_height': str(class_obj.scale_height)
            }
            preset['FLIP'] = {
                'flip': str(class_obj.flip),
                'flip_vh': str(class_obj.flip_vh)
            }
            preset['FILTERS'] = {
                'saturation': str(class_obj.saturation),
                'brightness': str(class_obj.brightness),
                'contrast': str(class_obj.contrast),
                'sharpen': str(class_obj.sharpen)
            }
            preset['AUTO'] = {
                'auto_bright': str(class_obj.auto_bright),
                'clip_hist_percent': str(class_obj.clip_hist_percent)
            }
            preset['GAMMA'] = {
                'gamma': str(class_obj.gamma)
            }
            preset['PREVIEW'] = {
                'preview_top': str(class_obj.preview_top),
                'preview_w': str(class_obj.preview_w),
                'preview_h': str(class_obj.preview_h)
            }


            with open(f_name, 'w') as conf:
                preset.write(conf)

            dialog.close()
            ui.notify(f'Preset saved for {class_name} as {f_name}', type='info')
        except Exception as e:
            cfg_mgr.logger.error(f'Error saving preset: {e}')
            ui.notify(f'Error saving preset: {e}', type='negative')

    with ui.dialog() as dialog:
        dialog.open()
        with ui.card():
            ui.label(class_name).classes('self-center')
            ui.separator()
            file_name = ui.input('Enter name', placeholder='preset name')
            with ui.row():
                ui.button('OK', on_click=lambda: save_file(file_name.value))
                ui.button('Cancel', on_click=dialog.close)

async def load_filter_preset(class_name: str, interactive: bool = True, file_name: str = None) -> bool:
    """
    Load and apply a preset configuration for a given class.

    Parameters:
    - class_name (str): The name of the class to load the preset for. Must be 'Desktop' or 'Media'.
    - interactive (bool): Whether to run in interactive mode. Default is True.
    - file_name (str, optional): The name of the preset file to load in non-interactive mode.

    Returns:
    - bool: True if the preset was applied successfully, False otherwise.
    """
    if class_name not in ['Desktop', 'Media']:
        cfg_mgr.logger.error(f'Unknown Class Name: {class_name}')
        return False

    def apply_preset_filter(preset_data: dict):
        try:
            class_obj = globals()[class_name]
            keys_to_check = [
                ('balance_r', 'RGB', 'balance_r', int),
                ('balance_g', 'RGB', 'balance_g', int),
                ('balance_b', 'RGB', 'balance_b', int),
                ('flip', 'FLIP', 'flip', str2bool_ini),
                ('flip_vh', 'FLIP', 'flip_vh', int),
                ('scale_width', 'SCALE', 'scale_width', int),
                ('scale_height', 'SCALE', 'scale_height', int),
                ('saturation', 'FILTERS', 'saturation', int),
                ('brightness', 'FILTERS', 'brightness', int),
                ('contrast', 'FILTERS', 'contrast', int),
                ('sharpen', 'FILTERS', 'sharpen', int),
                ('auto_bright', 'AUTO', 'auto_bright', str2bool_ini),
                ('clip_hist_percent', 'AUTO', 'clip_hist_percent', int),
                ('gamma', 'GAMMA', 'gamma', float),
                ('preview_top', 'PREVIEW', 'preview_top', str2bool_ini),
                ('preview_w', 'PREVIEW', 'preview_w', int),
                ('preview_h', 'PREVIEW', 'preview_h', int)
            ]

            for attr, section, key, *conversion in keys_to_check:
                try:
                    value = preset_data[section][key]
                    if conversion:
                        value = conversion[0](value)
                    setattr(class_obj, attr, value)
                except KeyError:
                    cfg_mgr.logger.warning(f'Key {section}.{key} does not exist in the preset data')

            if interactive:
                ui.notify('Preset applied', type='info')
            return True

        except Exception as er:
            cfg_mgr.logger.error(traceback.format_exc())
            cfg_mgr.logger.error(f'Error applying preset: {er}')
            ui.notify('Error applying preset', type='negative', position='center')
            return False

    if interactive:
        with ui.dialog() as dialog:
            dialog.open()
            with ui.card().classes('self-center'):
                ui.label(f'{class_name} Preset').classes('self-center')
                ui.separator()
                ui.button('EXIT', on_click=dialog.close)
                result = await LocalFilePicker(directory=cfg_mgr.app_root_path(f'config/presets/filter/{class_name}'),
                                               multiple=False,
                                               thumbs=False)
                if result is not None:
                    preset_filter_data = cfg.load(result[0]).to_dict()
                    ui.label(f'Preset name: {result}')
                    with ui.expansion('See values'):
                        await ui.json_editor({'content': {'json': preset_filter_data}}) \
                            .run_editor_method('updateProps',{'readOnly': True})
                    with ui.row():
                        ui.button('Apply', on_click=lambda: apply_preset_filter(preset_filter_data))
                    return True
                else:
                    ui.label('No preset selected')
                    return False

    else:

        try:
            preset_filter_data = cfg.load(cfg_mgr.app_root_path(f'config/presets/filter/{class_name}/{file_name}'))
            return apply_preset_filter(preset_filter_data)

        except Exception as e:
            cfg_mgr.logger.error(f'Error loading preset: {e}')
            return False


"""
END Filter preset mgr
"""


"""
Cast preset mgr
"""


def manage_cast_presets(class_name):
    """ Manage presets"""
    ui.button('save preset', on_click=lambda: save_cast_preset(class_name)).classes('w-20')
    ui.button('load preset', on_click=lambda: load_cast_preset(class_name)).classes('w-20')

async def save_cast_preset(class_name: str) -> None:
    """
    Save the current cast preset to an ini file.

    Parameters:
    - class_name (str): The name of the class to save the preset for. Must be 'Desktop' or 'Media'.
    """

    def save_file(f_name: str) -> None:
        if not f_name or not f_name.strip():
            ui.notify(f'Preset name could not be blank: {f_name}', type='negative')
            return

        f_name = cfg_mgr.app_root_path(f'config/presets/cast/{class_name}/{f_name}.ini')
        if os.path.isfile(f_name):
            ui.notify(f'Preset {f_name} already exists', type='warning')
            return

        try:
            class_obj = globals()[class_name]
            preset = configparser.ConfigParser()

            preset['GENERAL'] = {
                'rate': str(class_obj.rate),
                'stopcast': str(class_obj.stopcast),
                'scale_width': str(class_obj.scale_width),
                'scale_height': str(class_obj.scale_height),
                'wled': str(class_obj.wled),
                'wled_live': str(class_obj.wled_live),
                'host': str(class_obj.host),
                'viinput': str(class_obj.viinput)
            }

            preset['MULTICAST'] = {
                'multicast': str(class_obj.multicast),
                'cast_x': str(class_obj.cast_x),
                'cast_y': str(class_obj.cast_y),
                'cast_devices': str(class_obj.cast_devices)
            }

            if class_name == 'Desktop':
                preset['AREA'] = {
                    'monitor': str(class_obj.monitor_number),
                    'screen_coordinates': str(class_obj.screen_coordinates)
                }

            with open(f_name, 'w') as configfile:
                preset.write(configfile)

            dialog.close()
            ui.notify(f'Preset saved for {class_name} as {f_name}', type='info')
        except Exception as e:
            cfg_mgr.logger.error(f'Error saving preset: {e}')
            ui.notify(f'Error saving preset: {e}', type='negative')

    with ui.dialog() as dialog:
        dialog.open()
        with ui.card():
            ui.label(class_name).classes('self-center')
            ui.separator()
            file_name = ui.input('Enter name', placeholder='Preset name')

            with ui.row():
                ui.button('OK', on_click=lambda: save_file(file_name.value))
                ui.button('Cancel', on_click=dialog.close)

async def load_cast_preset(class_name: str, interactive: bool = True, file_name: str = None) -> bool:
    """
    Load and apply a cast preset configuration for a given class.

    Parameters:
    - class_name (str): The name of the class to load the preset for. Must be 'Desktop' or 'Media'.
    - interactive (bool): Whether to run in interactive mode. Default is True.
    - file_name (str, optional): The name of the preset file to load in non-interactive mode.

    Returns:
    - bool: True if the preset was applied successfully, False otherwise.
    """
    if class_name not in ['Desktop', 'Media']:
        cfg_mgr.logger.error(f'Unknown Class Name: {class_name}')
        return False

    def apply_preset_cast(preset_cast_data: dict):
        try:
            class_obj = globals()[class_name]
            keys_to_check = [
                ('rate', 'GENERAL', 'rate', int),
                ('stopcast', 'GENERAL', 'stopcast', str2bool_ini),
                ('scale_width', 'GENERAL', 'scale_width', int),
                ('scale_height', 'GENERAL', 'scale_height', int),
                ('wled', 'GENERAL', 'wled', str2bool_ini),
                ('wled_live', 'GENERAL', 'wled_live', str2bool_ini),
                ('host', 'GENERAL', 'host'),
                ('viinput', 'GENERAL', 'viinput', str2intstr_ini),
                ('multicast', 'MULTICAST', 'multicast', str2bool_ini),
                ('cast_x', 'MULTICAST', 'cast_x', int),
                ('cast_y', 'MULTICAST', 'cast_y', int),
                ('cast_devices', 'MULTICAST', 'cast_devices', str2list_ini),
                ('monitor', 'AREA', 'monitor', int),
                ('screen_coordinates', 'AREA', 'screen_coordinates', str2list_ini)
            ]

            # specific keys for Desktop
            if class_name == 'Desktop':
                keys_to_check.append(('monitor', 'AREA', 'monitor', int))
                keys_to_check.append(('screen_coordinates', 'AREA', 'screen_coordinates', str2list_ini))

            # apply new value and only warn if not exist
            # conversion is done if necessary
            for attr, section, key, *conversion in keys_to_check:
                try:
                    value = preset_cast_data[section][key]
                    if conversion:
                        value = conversion[0](value)
                    setattr(class_obj, attr, value)
                except KeyError:
                    cfg_mgr.logger.warning(f'Key {section}.{key} does not exist in the preset data')

            if interactive:
                ui.notify('Preset applied', type='info')
            return True

        except Exception as er:
            cfg_mgr.logger.error(traceback.format_exc())
            cfg_mgr.logger.error(f'Error applying preset: {er}')
            ui.notify('Error applying preset', type='negative', position='center')
            return False

    if interactive:
        with ui.dialog() as dialog:
            dialog.open()
            with ui.card().classes('self-center'):
                ui.label(f'{class_name} Preset').classes('self-center')
                ui.separator()
                ui.button('EXIT', on_click=dialog.close)
                result = await LocalFilePicker(directory=cfg_mgr.app_root_path(f'config/presets/cast/{class_name}'),
                                               multiple=False,
                                               thumbs=False)
                if result is not None:
                    preset_data = cfg.load(result[0]).to_dict()
                    ui.label(f'Preset name: {result}')
                    with ui.expansion('See values'):
                        await ui.json_editor({'content': {'json': preset_data}}) \
                            .run_editor_method('updateProps', {'readOnly': True})
                    with ui.row():
                        ui.button('Apply', on_click=lambda: apply_preset_cast(preset_data))
                    return True
                else:
                    ui.label('No preset selected')
                    return False
    else:

        try:
            preset_data = cfg.load(cfg_mgr.app_root_path(f'config/presets/cast/{class_name}/{file_name}'))
            return apply_preset_cast(preset_data)
        except Exception as e:
            cfg_mgr.logger.error(f'Error loading preset: {e}')
            return False


"""
END Cast preset mgr
"""

"""
Common Preset
"""


def str2bool_ini(value: str) -> bool:
    return str2bool(value)


def str2intstr_ini(value: str):
    try:
        value = int(value)
    except Exception:
        pass
    return value

def str2list_ini(value: str):
    try:
        value = ast.literal_eval(value)
    except Exception as e:
        cfg_mgr.logger.warning(f'Not able to convert to list: {value} Error : {e}')
    return value


"""
END Common
"""


async def player_cast(source):
    """ Cast from video CastAPI.player only for Media """

    media_info = CV2Utils.get_media_info(source)
    if Media.stopcast:
        ui.notify(f'Cast NOT allowed to run from : {source}', type='warning')
    else:
        Media.viinput = source
        Media.rate = int(round(float(media_info[2].split(':')[1].replace(' ', '').replace('"', ''))))
        ui.notify(f'Cast running from : {source}')
        Media.cast(shared_buffer=t_data_buffer)
    CastAPI.player.play()


async def cast_manage_page():
    """
    Cast parameters on the root page /
    :return:
    """

    with ui.card().tight().classes('self-center'):
        with ui.row():
            with ui.column(align_items='start', wrap=False):
                if Desktop.count > 0:
                    my_col = 'red'
                elif Desktop.stopcast:
                    my_col = 'yellow'
                else:
                    my_col = 'green'
                CastAPI.desktop_cast = ui.icon('cast', size='xl', color=my_col)
                CastAPI.desktop_cast.on('click', lambda: auth_cast(Desktop))
                CastAPI.desktop_cast_run = ui.button(icon='touch_app', on_click=lambda: init_cast(Desktop)) \
                    .classes('shadow-lg') \
                    .props(add='push size="md"') \
                    .tooltip('Initiate Desktop Cast')
                if Desktop.stopcast is True:
                    CastAPI.desktop_cast_run.set_visibility(False)

            ui.icon('stop_screen_share', size='xs', color='red') \
                .style('cursor: pointer') \
                .on('click', lambda: cast_stop(Desktop)).tooltip('Stop Cast')

            if str2bool(cfg_mgr.custom_config['animate-ui']):
                animated_card = Animate(ui.card, animation_name_in="fadeInUp", duration=2)
                card = animated_card.create_element()
            else:
                card = ui.card()
            card.classes('bg-red-900')

            with card:
                ui.label(' Running Cast(s) ').classes('self-center').style("color: yellow; background: purple")
                with ui.row():
                    desktop_count = ui.number(prefix='Desktop:').bind_value_from(Desktop, 'count')
                    desktop_count.classes("w-20")
                    desktop_count.props(remove='type=number', add='borderless')
                    media_count = ui.number(prefix='Media: ').bind_value_from(Media, 'count')
                    media_count.classes("w-20")
                    media_count.props(remove='type=number', add='borderless')

            ui.icon('stop_screen_share', size='xs', color='red') \
                .style('cursor: pointer') \
                .on('click', lambda: cast_stop(Media)).tooltip('Stop Cast')

            with ui.column(align_items='end', wrap=False):
                if Media.count > 0:
                    my_col = 'red'
                elif Media.stopcast:
                    my_col = 'yellow'
                else:
                    my_col = 'green'
                CastAPI.media_cast = ui.icon('cast', size='xl', color=my_col)
                CastAPI.media_cast.on('click', lambda: auth_cast(Media))
                CastAPI.media_cast_run = ui.button(icon='touch_app', on_click=lambda: init_cast(Media)) \
                    .classes('shadow-lg') \
                    .props(add='push size="md"') \
                    .tooltip('Initiate Media Cast')
                if Media.stopcast is True:
                    CastAPI.media_cast_run.set_visibility(False)


async def tabs_info_page():
    """ generate action/info page split by classes and show all running casts """

    # grab data
    info_data = await util_casts_info(img=True)
    # take only info data key
    info_data = info_data['t_info']
    # split desktop / media by using content of thread name
    desktop_threads = []
    media_threads = []
    for item in info_data:
        if 't_desktop_cast' in item:
            desktop_threads.append(item)
        elif 't_media_cast' in item:
            media_threads.append(item)

    """
    Tabs
    """

    if str2bool(cfg_mgr.custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)
        tabs_anim = Animate(ui.tabs, animation_name_in='backInDown', duration=1)
        tabs = tabs_anim.create_element()
    else:
        tabs = ui.tabs()

    tabs.classes('w-full')
    with tabs:
        p_desktop = ui.tab('Desktop', icon='computer').classes('bg-slate-400')
        p_media = ui.tab('Media', icon='image').classes('bg-slate-400')

        if Desktop.count > Media.count:
            tab_to_show = p_desktop
        elif Desktop.count < Media.count:
            tab_to_show = p_media
        else:
            tab_to_show = ''

    with (ui.tab_panels(tabs, value=tab_to_show).classes('w-full')):

        with ui.tab_panel(p_desktop):
            if not desktop_threads:
                ui.label('No CAST').classes('animate-pulse') \
                    .style('text-align:center; font-size: 150%; font-weight: 300')
            else:
                # create Graph
                graph_data = ''
                for item in desktop_threads:
                    t_id = info_data[item]["data"]["tid"]
                    t_name = item.replace(' ', '_').replace('(', '').replace(')', '')
                    graph_data += "WLEDVideoSync --> " + "|" + str(t_id) + "|" + t_name + "\n"
                with ui.row():
                    with ui.card():
                        ui.mermaid('''
                        graph LR;''' + graph_data + '''
                        ''')
                    await nice.generate_actions_to_cast('Desktop', desktop_threads, action_to_casts, info_data)

        with ui.tab_panel(p_media):
            if not media_threads:
                ui.label('No CAST').classes('animate-pulse') \
                    .style('text-align:center; font-size: 150%; font-weight: 300')
            else:
                # create Graph
                graph_data = ''
                for item in media_threads:
                    t_id = info_data[item]["data"]["tid"]
                    t_name = item.replace(' ', '_').replace('(', '').replace(')', '')
                    graph_data += "WLEDVideoSync --> " + "|" + str(t_id) + "|" + t_name + "\n"
                with ui.row():
                    with ui.card():
                        ui.mermaid('''
                        graph LR;''' + graph_data + '''
                        ''')
                    await nice.generate_actions_to_cast('Media', media_threads, action_to_casts, info_data)


async def action_to_casts(class_name, cast_name, action, params, clear, execute, data=None, exp_item=None):
    """ execute action from icon click and display a message """

    def valid_check():
        if circular.value:
            reverse.value= False
            random.value = False
            pause.value = False
            return 'circular'
        if reverse.value:
            circular.value = False
            random.value = False
            pause.value = False
            return 'reverse'
        if random.value:
            circular.value = False
            reverse.value = False
            pause.value = False
            return 'random'
        if pause.value:
            circular.value = False
            reverse.value = False
            random.value = False
            return 'pause'

    def valid_swap():
        type_effect = valid_check()
        if type_effect is None:
            # stop effects
            action_to_thread(class_name, cast_name, action, 'stop', clear, execute=True)
            ui.notify('Effect stop & Reset to initial')
        else:
            ui.notify(f'Initiate effect: {type_effect}')
            action_to_thread(
                class_name,
                cast_name,
                action,
                f'{type_effect},{int(new_delay.value)}',
                clear,
                execute=True,
            )

    def valid_ip():
        if new_ip.value == '127.0.0.1' or Utils.check_ip_alive(new_ip.value, ping=True):
            # put to loopback if cast(s) with same IP already exist, and we do not want multi
            if multi.value is False:
                name = None
                for thread_name, thread_info in data.items():
                    cast_type = thread_info['data'].get('cast_type', 'unknown')  # Default to 'unknown' if not specified
                    if cast_type == 'CASTDesktop':
                        name = 'Desktop'
                    elif cast_type == 'CASTMedia':
                        name = 'Media'
                    devices = thread_info['data'].get('devices', [])
                    multicast = thread_info['data'].get('multicast', True)  # Default to True if not specified
                    # put new IP and action in wait mode
                    if new_ip.value in devices and not multicast:
                        data[thread_name]['data']['devices'][0] = '127.0.0.1'
                        action_to_thread(name, thread_name, action, '127.0.0.1', clear, execute=False)
            # put new IP and execute action
            data[cast_name]['data']['devices'][0] = new_ip.value
            action_to_thread(class_name, cast_name, action, new_ip.value, clear, execute=True)
            ui.notification('IP address applied', type='positive', position='center', timeout=2)
        else:
            ui.notification('Bad IP address or not reachable', type='negative', position='center', timeout=2)

    if action == 'host':
        with ui.dialog() as dialog, ui.card() as ip_card:
            dialog.open()
            ip_card.classes('w-full')
            with ui.row():
                new_ip = ui.input('IP',placeholder='Enter new IP address', value='127.0.0.1')
                multi = ui.checkbox('allow multiple', value=False)
                multi.tooltip('Check to let Cast(s) with same Device/IP to continue stream')
            ui.button('OK', on_click=valid_ip)

        ui.notification(f'Change IP address for  {cast_name}...', type='info', position='top', timeout=2)

    elif action == 'multicast':
        with ui.dialog() as dialog, ui.card() as ip_card:
            dialog.open()
            ip_card.classes('w-full')
            with ui.row():
                new_delay = ui.number('Delay',
                                      placeholder='Delay in ms',
                                      value=1000,
                                      min=1,
                                      max=100000,
                                      precision=0)
                new_delay.tooltip('how long between swapping')
                circular = ui.checkbox('circular', value=False, on_change=valid_check)
                circular.tooltip('Swap IP one by one (circular)')
                reverse = ui.checkbox('reverse', value=False, on_change=valid_check)
                reverse.tooltip('Swap IP one by one in reverse order (reverse)')
                random = ui.checkbox('random', value=False, on_change=valid_check)
                random.tooltip('Swap IP randomly (random)')
                pause = ui.checkbox('Pause random', value=False, on_change=valid_check)
                pause.tooltip('Pause Cast/IP randomly (pause)')

            ui.button('OK', on_click=valid_swap).tooltip('Validate, if nothing checked stop and set IP to initial')

    else:

        action_to_thread(class_name, cast_name, action, params, clear, execute)

        if action == 'stop':
            exp_item.close()
            ui.notification(f'Stopping {cast_name}...', type='warning', position='center', timeout=1)
            exp_item.delete()
            del data[cast_name]
        elif action == 'shot':
            ui.notification(f'Saving image to buffer for  {cast_name}...', type='positive', timeout=1)
        elif action == 'close-preview':
            ui.notification(f'Preview window terminated for  {cast_name}...', type='info', timeout=1)
        else:
            ui.notification(f'Initiate {action} with params {params} for {cast_name}...', type='info', timeout=1)


async def show_thread_info():
    """ show all info from running cats """

    dialog = ui.dialog().props(add='transition-show="slide-down" transition-hide="slide-up"')
    with dialog, ui.card():
        cast_info = await util_casts_info()
        editor = ui.json_editor({'content': {'json': cast_info}}) \
            .run_editor_method('updateProps', {'readOnly': True})
        ui.button('Close', on_click=dialog.close, color='red')
        dialog.open()


async def root_timer_action():
    """
    timer action occur only when root page is active /
    :return:
    """

    nice.sync_button(CastAPI, Media)

    nice.cast_manage(CastAPI, Desktop, Media)

    if str2bool(cfg_mgr.custom_config['system-stats']):
        await nice.system_stats(CastAPI, Desktop, Media)


async def info_timer_action():
    """
    timer action occur only when info page is active '/info'
    :return:
    """

    nice.cast_manage(CastAPI, Desktop, Media)


async def player_timer_action():
    """
    timer action occur when player is displayed
    :return:
    """
    nice.sync_button(CastAPI, Media)


async def cast_to_wled(class_obj, image_number):
    """
    Cast to wled from GUI
    used on the buffer images
    """

    if not class_obj.wled:
        ui.notify('No WLED device', type='negative', position='center')
        return

    if is_alive := Utils.check_ip_alive(class_obj.host):
        ui.notify(f'Cast to device : {class_obj.host}')
        if class_obj.__module__ == 'desktop':
            class_name = 'Desktop'
        elif class_obj.__module__ == 'media':
            class_name = 'Media'
        else:
            class_name = 'unknown'

        # select buffer for image to send
        buffer_name = 'multicast' if class_obj.multicast else 'buffer'
        # send image
        cast_image(
            image_number=image_number,
            device_number=-1,
            class_name=class_name,
            fps_number=25,
            duration_number=1000,
            retry_number=1,
            buffer_name=buffer_name
        )
    else:
        cfg_mgr.logger.warning('Device do not accept connection to port 80')
        ui.notify('Device do not accept connection to port 80', type='warning')


async def discovery_net_notify():
    """ Call Run zero conf net discovery """

    ui.notification('NET Discovery process on go ... let it finish',
                    close_button=True,
                    type='warning',
                    timeout=6)
    await run_in_threadpool(Netdevice.discover)
    # net_view_page.refresh()


async def discovery_media_notify():
    """ Call Run OS Media discovery by av """

    ui.notification('MEDIA Discovery process on go ... let it finish',
                    close_button=True,
                    type='warning',
                    timeout=3)
    Utils.dev_list_update()


async def init_cast(class_obj):
    """
    Run the cast and refresh the cast view
    :param class_obj:
    :return:
    """
    class_obj.cast(shared_buffer=t_data_buffer)
    nice.cast_manage(CastAPI, Desktop, Media)
    cfg_mgr.logger.debug(f'Run Cast for {str(class_obj)}')
    ui.notify(f'Cast initiated for :{str(class_obj)}')


async def cast_stop(class_obj):
    """ Stop cast """

    class_obj.stopcast = True
    ui.notify(f'Cast(s) stopped and blocked for : {class_obj}', position='center', type='info', close_button=True)
    nice.cast_manage(CastAPI, Desktop, Media)
    cfg_mgr.logger.debug(f' Stop Cast for {str(class_obj)}')


async def auth_cast(class_obj):
    """ Authorized cast """

    class_obj.stopcast = False
    ui.notify(f'Cast(s) Authorized for : {class_obj}', position='center', type='info', close_button=True)
    nice.cast_manage(CastAPI, Desktop, Media)
    cfg_mgr.logger.debug(f' Cast auth. for {str(class_obj)}')


async def light_box_image(index, image, txt1, txt2, class_obj, buffer):
    """
    Provide basic 'lightbox' effect for image
    :param buffer:
    :param class_obj:
    :param index:
    :param image:
    :param txt1:
    :param txt2:
    :return:
    """
    with ui.card():
        try:
            with ui.image(image):
                if txt1 != '' or txt2 != '':
                    ui.label(txt1).classes('absolute-bottom text-subtitle2 text-center')
                    ui.label(txt2).classes('absolute-bottom text-subtitle2 text-center')
                ui.label(str(index))

            dialog = ui.dialog().style('width: 800px')
            with dialog:
                ui.label(str(index)) \
                    .tailwind.font_weight('extrabold').text_color('red-600').background_color('orange-200')
                with ui.interactive_image(image):
                    with ui.row().classes('absolute top-0 left-0 m-2'):
                        ui.button(on_click=lambda: cast_to_wled(class_obj, index), icon='cast') \
                            .props('flat fab color=white') \
                            .tooltip('Cast to WLED')
                        ui.button(on_click=lambda: CV2Utils.save_image(class_obj, buffer, index, False), icon='save') \
                            .props('flat fab color=white') \
                            .tooltip('Save Image')
                        ui.button(on_click=lambda: CV2Utils.save_image(class_obj, buffer, index, True),
                                  icon='text_format') \
                            .props('flat fab color=white') \
                            .tooltip('Save Image as Ascii ART')

                    ui.label(str(index)).classes('absolute-bottom text-subtitle2 text-center').style('background: red')
                ui.button('Close', on_click=dialog.close, color='red')
            ui.button('', icon='preview', on_click=dialog.open, color='bg-red-800').tooltip('View image')

        except Exception as im_error:
            cfg_mgr.logger.error(traceback.format_exc())
            cfg_mgr.logger.error(f'An exception occurred: {im_error}')


async def bar_get_size():
    """ Read data from YT download, loop until no more data to download """

    while True:
        if Utils.yt_file_size_remain_bytes == 0:
            break

        else:

            CastAPI.progress_bar.value = 1 - (Utils.yt_file_size_remain_bytes / Utils.yt_file_size_bytes)
            CastAPI.progress_bar.update()
            await sleep(.1)


async def download_url(url):
    """ Download video/image from Web url """

    video_img_url = url
    CastAPI.progress_bar.value = 0
    CastAPI.progress_bar.update()

    # check if YT Url
    if 'https://www.youtu' in url:

        # this will run async loop in background and continue...
        create_task(bar_get_size())

        # wait YT download finished
        yt = await Utils.youtube_download(url, interactive=True)

        # if no error, set local YT file name to video player
        if yt != '':
            video_img_url = yt

    elif await Utils.is_image_url(url):

        # generate a unique name
        # Get the current date and time
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Format the unique name with prefix, date, time, and extension
        image_name = f"image-tmp_{current_time}.jpg"

        result = await Utils.download_image(cfg_mgr.app_root_path('media'), url, image_name)
        if result:
            video_img_url = cfg_mgr.app_root_path(f'media/{image_name}')

    ui.notify(f'Video set to : {video_img_url}')
    cfg_mgr.logger.debug(f'Video set to : {video_img_url}')

    # put max value to progress bar
    CastAPI.progress_bar.value = 1
    CastAPI.progress_bar.update()
    # set video player media
    CastAPI.player.set_source(video_img_url)
    CastAPI.player.update()


"""
Customization
"""


def custom_openapi():
    """ got ws page into FastAPI docs """

    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="WLEDVideoSync",
        version="1.0.0",
        description="API docs",
        routes=app.routes,
    )
    # Add WebSocket route to the schema
    openapi_schema["paths"]["/ws/docs"] = {
        "get": {
            "summary": "webSocket - only for reference",
            "description": websocket_info,
            "responses": {200: {}},
            "tags": ["websocket"]
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def apply_custom():
    """
    Layout Colors come from config file
    bg image can be customized
    :return:
    """
    ui.colors(primary=cfg_mgr.color_config['primary'],
              secondary=cfg_mgr.color_config['secondary'],
              accent=cfg_mgr.color_config['accent'],
              dark=cfg_mgr.color_config['dark'],
              positive=cfg_mgr.color_config['positive'],
              negative=cfg_mgr.color_config['negative'],
              info=cfg_mgr.color_config['info'],
              warning=cfg_mgr.color_config['warning']
              )

    # custom font (experimental)
    font_file = cfg_mgr.app_config['font_file']
    if font_file != '':
        FontSetApplication(font_path=font_file, size_adjust='100%')

    # custom bg
    ui.query('body').style(f'background-image: url({cfg_mgr.custom_config["bg-image"]}); '
                           'background-size: cover;'
                           'background-repeat: no-repeat;'
                           'background-position: center;')


"""
RUN
"""

# settings
app.openapi = custom_openapi
app.add_static_files('/assets', cfg_mgr.app_root_path('assets'))
app.add_media_files('/media', cfg_mgr.app_root_path('media'))
app.add_static_files('/log', cfg_mgr.app_root_path('log'))
app.add_static_files('/config', cfg_mgr.app_root_path('config'))
app.add_static_files('/tmp', cfg_mgr.app_root_path('tmp'))
app.add_static_files('/xtra', cfg_mgr.app_root_path('xtra'))
app.on_startup(init_actions)

# choose GUI
native_ui = cfg_mgr.app_config['native_ui']
native_ui_size = cfg_mgr.app_config['native_ui_size']
show = None
try:
    if native_ui.lower() == 'none':
        native_ui_size = None
        native_ui = False
        show = False
    elif str2bool(native_ui):
        native_ui = True
        native_ui_size = tuple(native_ui_size.split(','))
        native_ui_size = (int(native_ui_size[0]), int(native_ui_size[1]))
    else:
        show = True
        native_ui_size = None
        native_ui = False
except Exception as error:
    cfg_mgr.logger.error(f'Error in config file for native_ui : {native_ui} - {error}')
    sys.exit(1)

# run app
ui.run(title='WLEDVideoSync',
       favicon=cfg_mgr.app_root_path('favicon.ico'),
       host=server_ip,
       port=server_port,
       fastapi_docs=str2bool(cfg_mgr.app_config['fastapi_docs']),
       show=show,
       reconnect_timeout=int(cfg_mgr.server_config['reconnect_timeout']),
       reload=False,
       native=native_ui,
       window_size=native_ui_size,
       access_log=False)

"""
END
"""

# some cleaning
cfg_mgr.logger.info('Cleaning ...')
cfg_mgr.logger.debug('Remove tmp files')
for tmp_filename in PathLib("tmp/").glob("*_file.*"):
    tmp_filename.unlink()

# remove yt files
if str2bool(cfg_mgr.app_config['keep_yt']) is not True:
    for media_filename in PathLib("media/").glob("yt-tmp-*.*"):
        media_filename.unlink()

# remove image files
if str2bool(cfg_mgr.app_config['keep_image']) is not True:
    for img_filename in PathLib("media/").glob("image-tmp_*_*.jpg"):
        img_filename.unlink()

