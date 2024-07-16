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
import logging
import logging.config
import concurrent_log_handler
import threading
import traceback
import multiprocessing
import asyncio
from subprocess import Popen

from ddp_queue import DDPDevice

import time
import sys
import os
import socket
import json
import cv2
import configparser
from pathlib import Path as PathLib

import queue

import cfg_load as cfg

import desktop
import media

from utils import CASTUtils as Utils, LogElementHandler
from utils import HTTPDiscovery as Net
from utils import ImageUtils
from utils import LocalFilePicker
from utils import ScreenAreaSelection as Sa
from utils import YtSearch
from utils import AnimatedElement as Animate

import ast

from datetime import datetime
from str2bool import str2bool

from PIL import Image

from fastapi.openapi.utils import get_openapi
from fastapi import HTTPException, Path, WebSocket
from starlette.concurrency import run_in_threadpool

from nicegui import app, ui, native, context
from nicegui.events import ValueChangeEventArguments

"""
Main test for platform
    MacOS need specific case
    Linux(POSIX) - Windows use the same 
"""
if sys.platform == 'darwin':
    ctx = multiprocessing.get_context('spawn')
    Process = ctx.Process
    Queue = ctx.Queue
else:
    Process = multiprocessing.Process
    Queue = multiprocessing.Queue

Desktop = desktop.CASTDesktop()
Media = media.CASTMedia()
Netdevice = Net()

class_to_test = ['Desktop', 'Media', 'Netdevice']
action_to_test = ['stop', 'shot', 'info', 'close_preview', 'open_preview', 'reset']

app.debug = False
log_ui = None

"""
When this env var exist, this mean run from the one-file compressed executable.
Load of the config is not possible, folder config should not exist yet.
This avoid FileNotFoundError.
This env not exist when run from the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    # read config
    # create logger
    logger = Utils.setup_logging('config/logging.ini', 'WLEDLogger.api')

    # load config file
    cast_config = Utils.read_config()

    # config keys
    server_config = cast_config[0]  # server key
    app_config = cast_config[1]  # app key
    color_config = cast_config[2]  # colors key
    custom_config = cast_config[3]  # custom key
    preset_config = cast_config[4]  # presets key

    # load optional modules
    if str2bool(custom_config['player']) or str2bool(custom_config['system-stats']):
        import psutil

        if str2bool(custom_config['player']):
            from pytube import YouTube

    #  validate network config
    server_ip = server_config['server_ip']
    if not Utils.validate_ip_address(server_ip):
        logger.error(f'Bad server IP: {server_ip}')
        sys.exit(1)

    server_port = server_config['server_port']

    if server_port == 'auto':
        server_port = native.find_open_port()
    else:
        server_port = int(server_config['server_port'])

    if server_port not in range(1, 65536):
        logger.error(f'Bad server Port: {server_port}')
        sys.exit(2)


    async def init_actions():
        """ Done at start of app and before GUI available"""

        # Apply presets
        try:
            if str2bool(preset_config['load_at_start']):
                if preset_config['filter_media'] != '':
                    logger.info(f"apply : {preset_config['filter_media']} to filter Media")
                    await load_filter_preset('Media', interactive=False, file_name=preset_config['filter_media'])
                if preset_config['filter_desktop'] != '':
                    logger.info(f"apply : {preset_config['filter_desktop']} to filter Desktop")
                    await load_filter_preset('Desktop', interactive=False, file_name=preset_config['filter_desktop'])
                if preset_config['cast_media'] != '':
                    logger.info(f"apply : {preset_config['cast_media']} to cast Media")
                    await load_cast_preset('Media', interactive=False, file_name=preset_config['cast_media'])
                if preset_config['cast_desktop'] != '':
                    logger.info(f"apply : {preset_config['cast_desktop']} to cast Desktop")
                    await load_cast_preset('Desktop', interactive=False, file_name=preset_config['cast_desktop'])

        except Exception as error:
            logger.error(f"Error on app startup {error}")


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


"""
FastAPI
"""


@app.get("/api", tags=["root"])
async def read_api_root():
    """
        Status: see if WLEDVideoSync is running
    """

    return {"Status": "WLEDVideoSync is Running ..."}


@app.get("/api/{class_obj}/params", tags=["params"])
async def all_params(class_obj: str = Path(description=f'Class name, should be in: {class_to_test}')):
    """
        Retrieve all 'params/attributes' from a class
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")
    class_params = vars(globals()[class_obj])
    # to avoid delete param from the class, need to copy to another dict
    return_data = {k: v for k, v in class_params.items()}
    if class_obj != 'Netdevice':
        del return_data['frame_buffer']
        del return_data['cast_frame_buffer']
        del return_data['ddp_multi_names']
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
    except KeyError:
        raise HTTPException(status_code=400,
                            detail=f"Invalid class name: {class_name}")

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
            logger.info("viinput act as string only")

    # append title if needed
    if class_name == 'Desktop' and param == 'viinput' and sys.platform == 'win32':
        if value not in ['desktop', 'area']:
            value = 'title=' + value

    # check valid IP
    if param == 'host':
        is_valid = Utils.validate_ip_address(value)
        if not is_valid:
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' must be IP address")

    # check cast devices comply to [(0,'IP'), ... ]
    if param == 'cast_devices':
        is_valid = Utils.is_valid_cast_device(str(value))
        if not is_valid:
            raise HTTPException(status_code=400,
                                detail=f"Value '{value}' for attribute '{param}' not comply to list [(0,'IP'),...]")

    # set new value to class attribute
    setattr(class_obj, param, value)
    return {"message": f"Attribute '{param}' updated successfully for : '{class_obj}'"}


@app.get("/api/{class_obj}/buffer", tags=["buffer"])
async def buffer_count(class_obj: str = Path(description=f'Class name, should be in: {class_to_test}')):
    """
        Retrieve frame buffer length from a class (image number)
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")
    class_name = globals()[class_obj]

    return {"buffer_count": len(class_name.frame_buffer)}


@app.get("/api/{class_obj}/buffer/{number}", tags=["buffer"])
async def buffer_image(class_obj: str = Path(description=f'Class name, should be in: {class_to_test}'),
                       number: int = 0):
    """
        Retrieve image number from buffer class, result base64 image
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")

    try:
        class_name = globals()[class_obj]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid Class name: {class_obj}")

    if number > len(class_name.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_obj} ")

    try:
        img = ImageUtils.image_array_to_base64(class_name.frame_buffer[number])
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} provide this error : {error}")

    return {"buffer_base64": img}


@app.get("/api/{class_obj}/buffer/{number}/save", tags=["buffer"])
async def buffer_image_save(class_obj: str = Path(description=f'Class name, should be in: {class_to_test}'),
                            number: int = 0):
    """
        Retrieve image number from buffer class, save it to default folder
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")

    try:
        class_name = globals()[class_obj]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid Class name: {class_obj}")

    if number > len(class_name.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_obj} ")

    try:
        await save_image(class_name, 'frame_buffer', number)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} provide this error : {error}")

    return {"buffer_save": True}


@app.get("/api/{class_obj}/buffer/{number}/asciiart/save", tags=["buffer"])
async def buffer_image_save_ascii(class_obj: str = Path(description=f'Class name, should be in: {class_to_test}'),
                                  number: int = 0):
    """
        Retrieve image number from buffer class, save it to default folder as ascii_art
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")

    try:
        class_name = globals()[class_obj]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid Class name: {class_obj}")

    if number > len(class_name.frame_buffer):
        raise HTTPException(status_code=400, detail=f"Image number : {number} not exist for Class name: {class_obj} ")

    try:
        await save_image(class_name, 'frame_buffer', number, ascii_art=True)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} provide this error : {error}")

    return {"buffer_save": True}


@app.get("/api/{class_obj}/run_cast", tags=["casts"])
async def run_cast(class_obj: str = Path(description=f'Class name, should be in: {class_to_test}')):
    """
      Run the cast() from {class_obj}
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")
    try:
        my_obj = globals()[class_obj]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid Class name: {class_obj}")

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
    status = "Error"
    if Utils.dev_list_update():
        status = "Ok"
    return {"device_list": status}


@app.get("/api/util/download_yt/{yt_url:path}", tags=["media"])
async def util_download_yt(yt_url: str):
    """
       Download video from Youtube Url
    """

    if 'https://youtu' in yt_url:

        yt = YouTube(
            url=yt_url,
            use_oauth=False,
            allow_oauth_cache=True
        )

        try:

            # this usually should select the first 720p video, enough for cast
            prog_stream = yt.streams.filter(progressive=True).order_by('resolution').desc().first()
            # initiate download to tmp folder
            prog_stream.download(output_path='tmp', filename_prefix='yt-tmp-', timeout=3, max_retries=2)

        except Exception as error:
            logger.info(f'youtube error: {error}')
            raise HTTPException(status_code=400,
                                detail=f"Not able to retrieve video from : {yt_url} {error}")
    else:
        raise HTTPException(status_code=400,
                            detail=f"Looks like not YT url : {yt_url} ")

    return {"youtube": 'ok'}


@app.get("/api/util/device_net_scan", tags=["network"])
async def util_device_net_scan():
    """
        Scan network devices with zeroconf
    """
    # run in non-blocking mode
    await run_in_threadpool(Netdevice.discover)
    return {"net_device_list": 'done'}


@app.get("/api/util/blackout", tags=["utility"])
async def util_blackout():
    """
        Put ALL ddp devices Off and stop all Casts
    """
    logger.warning('** BLACKOUT **')
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

    return {"blackout": 'done'}


@app.get("/api/util/casts_info", tags=["casts"])
def util_casts_info():
    """
        Get info from all Cast Threads
    """
    logger.debug('Request Cast(s) info')

    # clear
    child_info_data = {}
    child_list = []

    for item in Desktop.cast_names:
        child_list.append(item)
        Desktop.cast_name_todo.append(str(item) + '||' + 'info' + '||' + str(time.time()))
    for item in Media.cast_names:
        child_list.append(item)
        Media.cast_name_todo.append(str(item) + '||' + 'info' + '||' + str(time.time()))

    # request info from threads
    Desktop.t_todo_event.set()
    Media.t_todo_event.set()

    # use to stop the loop in case of
    start_time = time.time()
    logger.debug(f'Need to receive info from : {child_list}')

    # iterate through all Cast Names
    for item in child_list:
        # wait and get info dict from a thread
        try:
            data = t_data_buffer.get(timeout=3)
            child_info_data.update(data)
            t_data_buffer.task_done()
        except queue.Empty:
            logger.error('Empty queue, but Desktop/Media cast names list not')
            break

    # sort the dict
    sort_child_info_data = dict(sorted(child_info_data.items()))

    Desktop.t_todo_event.clear()
    Media.t_todo_event.clear()
    logger.debug('End request info')

    return {"t_info": sort_child_info_data}


@app.get("/api/{class_name}/list_actions", tags=["casts"])
async def list_todo_actions(class_name: str = Path(description=f'Class name, should be in: {class_to_test}')):
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
    except KeyError:
        raise HTTPException(status_code=400,
                            detail=f"Invalid class name: {class_name}")

    if not hasattr(class_obj, 'cast_name_todo'):
        raise HTTPException(status_code=400,
                            detail=f"Invalid attribute name")

    return {"actions": class_obj.cast_name_todo}


@app.put("/api/{class_name}/cast_actions", tags=["casts"])
async def action_to_thread(class_name: str = Path(description=f'Class name, should be in: {class_to_test}'),
                           cast_name: str = None,
                           action: str = None,
                           clear: bool = False,
                           execute: bool = False):
    """
    Add action to cast_name_todo for a specific Cast
    If clear, remove all to do
    :param execute: instruct casts to execute action in to do list
    :param clear: Remove all actions from to do list
    :param class_name:
    :param cast_name:
    :param action:
    :return:
    """

    if class_name not in class_to_test:
        logger.error(f"Class name: {class_name} not in {class_to_test}")
        raise HTTPException(status_code=400,
                            detail=f"Class name: {class_name} not in {class_to_test}")
    try:
        class_obj = globals()[class_name]
    except KeyError:
        logger.error(f"Invalid class name: {class_name}")
        raise HTTPException(status_code=400,
                            detail=f"Invalid class name: {class_name}")

    if cast_name is not None and cast_name not in class_obj.cast_names:
        logger.error(f"Invalid Cast name: {cast_name}")
        raise HTTPException(status_code=400,
                            detail=f"Invalid Cast name: {cast_name}")

    if not hasattr(class_obj, 'cast_name_todo'):
        logger.error(f"Invalid attribute name")
        raise HTTPException(status_code=400,
                            detail=f"Invalid attribute name")

    if clear:
        class_obj.cast_name_todo = []
        logger.debug(f" To do cleared for {class_obj}'")
        return {"message": f" To do cleared for {class_obj}'"}

    if action not in action_to_test and action is not None:
        logger.error(f"Invalid action name. Allowed : " + str(action_to_test))
        raise HTTPException(status_code=400,
                            detail=f"Invalid action name. Allowed : " + str(action_to_test))

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
            logger.error(f"Invalid Cast/Thread name or action not set")
            raise HTTPException(status_code=400,
                                detail=f"Invalid Cast/Thread name or action not set")
        else:
            class_obj.cast_name_todo.append(str(cast_name) + '||' + str(action) + '||' + str(time.time()))
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            logger.debug(f"Action '{action}' added successfully to : '{class_obj}'")
            return {"message": f"Action '{action}' added successfully to : '{class_obj}'"}

    else:

        if cast_name is None and action is None:
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            class_obj.t_todo_event.set()
            logger.debug(f"Actions in queue will be executed")
            return {"message": f"Actions in queue will be executed"}

        elif cast_name is None or action is None:
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            logger.error(f"Invalid Cast/Thread name or action not set")
            raise HTTPException(status_code=400,
                                detail=f"Invalid Cast/Thread name or action not set")

        else:

            class_obj.cast_name_todo.append(str(cast_name) + '||' + str(action) + '||' + str(time.time()))
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            class_obj.t_todo_event.set()
            logger.debug(f"Action '{action}' added successfully to : '{class_obj} and execute is On'")
            return {"message": f"Action '{action}' added successfully to : '{class_obj} and execute is On'"}


@app.get("/api/config/presets/{file_name}/{class_name}", tags=["presets"])
async def apply_preset_api(class_name: str = Path(description=f'Class name, should be in: {class_to_test}'),
                           file_name: str = None):
    """
    Apply preset to Class name from saved one
    :param class_name:
    :param file_name: preset name
    :return:
    """
    if class_name not in class_to_test:
        raise HTTPException(status_code=400,
                            detail=f"Class name: {class_name} not in {class_to_test}")
    try:
        class_obj = globals()[class_name]
    except KeyError:
        raise HTTPException(status_code=400,
                            detail=f"Invalid class name: {class_name}")
    try:
        result = await load_filter_preset(class_name=class_name, interactive=False, file_name=file_name)
        if result is False:
            raise HTTPException(status_code=400,
                                detail=f"Apply preset return value : {result}")
    except Exception as error:
        raise HTTPException(status_code=400,
                            detail=f"Not able to apply preset : {error}")

    return {"apply_preset_result": True}


"""
FastAPI WebSockets
"""

websocket_info = 'These are the websocket end point calls and result'


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WS image Cast (we use Websocket to minimize delay)
    Main logic: check action name, extract params, execute func, return ws status
    :param websocket:
    :return:
    """
    # list of managed actions
    allowed_actions = ['cast_image']

    # Main WS
    try:
        # accept connection
        await websocket.accept()

        while True:
            # wait for data (need to be in json format)
            data = await websocket.receive_text()

            # once received, decode json
            json_data = json.loads(data)

            # validate data format received
            if not Utils.validate_ws_json_input(json_data):
                logger.error('WEBSOCKET: received data not compliant with expected format')
                await websocket.send_text('{"result":"error"}')
                raise Exception

            # select action to do
            action = json_data["action"]["type"]

            # creating parameter list programmatically
            params = json_data["action"]["param"]  # param dict
            if action in allowed_actions:
                # get all params

                # these are required
                image_number = json_data["action"]["param"]["image_number"]
                params["image_number"] = image_number
                device_number = json_data["action"]["param"]["device_number"]
                params["device_number"] = device_number
                class_name = json_data["action"]["param"]["class_name"]
                params["class_name"] = class_name

                # these are optionals
                if "fps_number" in json_data:
                    fps_number = json_data["action"]["param"]["fps_number"]
                    if fps_number > 60:
                        fps_number = 60
                    elif fps_number < 0:
                        # 0 here is allowed for action cast_image
                        fps_number = 0
                    params["fps_number"] = fps_number
                if "duration_number" in json_data:
                    duration_number = json_data["action"]["param"]["duration_number"]
                    if duration_number < 0:
                        duration_number = 0
                    params["duration_number"] = duration_number
                if "retry_number" in json_data:
                    retry_number = json_data["action"]["param"]["retry_number"]
                    if retry_number > 10:
                        retry_number = 10
                    elif retry_number < 0:
                        retry_number = 0
                    params["retry_number"] = retry_number
                if "buffer_name" in json_data:
                    buffer_name = json_data["action"]["param"]["buffer_name"]
                    params["buffer_name"] = buffer_name

                # execute action with params
                # response = await run.io_bound(requests.get, URL, timeout=3)
                # result = await run.io_bound(globals()[action], **params,)
                await globals()[action](**params)
                # send back if no problem
                await websocket.send_text('{"result":"success"}')

            else:

                logger.error('WEBSOCKET: received data contain unexpected action')
                await websocket.send_text('{"result":"error"}')
                raise Exception

    except Exception as error:
        logger.error(traceback.format_exc())
        logger.error(f'WEBSOCKET An exception occurred: {error}')
        await websocket.send_text('{"result":"internal error"}')
        await websocket.close()


async def cast_image(image_number,
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
    print(class_obj)

    """
    on 10/04/2024: device_number come from list entry order (0...n)
    """
    if device_number == -1:  # instruct to use IP from the class.host
        ip = socket.gethostbyname(class_obj.host)
    else:
        ip = socket.gethostbyname(class_obj.cast_devices[device_number][1])

    if ip == '127.0.0.1':
        logger.warning('Nothing to do for localhost 127.0.0.1')
        return

    if buffer_name.lower() == 'buffer':
        images_buffer = class_obj.frame_buffer
    elif buffer_name.lower() == 'multicast':
        images_buffer = class_obj.cast_frame_buffer

    logger.info('Cast one image from buffer')
    logger.info(f"image number: {image_number}")
    logger.info(f"device number: {device_number}")
    logger.info(f"FPS: {fps_number}")
    logger.info(f"Duration (in ms):  {duration_number}")
    logger.info(f"retry frame number:  {retry_number}")
    logger.info(f"class name: {class_name}")
    logger.info(f"Image from buffer: {buffer_name}")

    ddp = DDPDevice(ip)

    start_time = time.time() * 1000  # Get the start time in ms
    end_time = start_time + duration_number  # Calculate the end time

    if class_obj.protocol == "ddp":
        while time.time() * 1000 < end_time:  # Loop until current time exceeds end time in ms
            # Send x frames here
            ddp.send_to_queue(images_buffer[image_number], retry_number)
            if fps_number != 0:
                time.sleep(1 / fps_number)  # Sleep in s for the time required to send one frame


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

    if str2bool(custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)

    """
    timer created on main page run to refresh datas
    """
    main_timer = ui.timer(int(app_config['timer']), callback=root_timer_action)

    """
    Header with button menu
    """
    with ui.header(bordered=True, elevated=True).classes('items-center shadow-lg'):
        ui.link('MAIN', target='/').classes('text-white text-lg font-medium')
        ui.icon('home')
        # Create buttons
        ui.button('Manage', on_click=lambda: ui.navigate.to('/Manage'), icon='video_settings')
        ui.button('Desktop Params', on_click=lambda: ui.navigate.to('/Desktop'), icon='computer')
        ui.button('Media Params', on_click=lambda: ui.navigate.to('/Media'), icon='image')
        ui.button('API', on_click=lambda: ui.navigate.to('/docs', new_tab=True), icon='api')

    """
    App info
    """
    if str2bool(custom_config['animate-ui']):
        head_row_anim = Animate(ui.row, animation_name_in='backInDown', duration=1)
        head_row = head_row_anim.create_element()
    else:
        head_row = ui.row()

    with head_row.classes('w-full no-wrap'):
        ui.label('DESKTOP: Cast Screen / Window content').classes('bg-slate-400 w-1/3')
        with ui.card().classes('bg-slate-400 w-1/3'):
            ui.image("/assets/favicon.ico").classes('self-center').tailwind.border_width('8').width('8')
        ui.label('MEDIA: Cast Image / Video / Capture Device (e.g. USB Camera ...)').classes('bg-slate-400 w-1/3')

    ui.separator().classes('mt-6')
    ui.image("./assets/Source-intro.png").classes('self-center').tailwind.border_width('8').width('1/6')

    """
    Video player
    """
    if str2bool(custom_config['player']):
        await video_player_page()
        CastAPI.player.set_visibility(False)

    """
    Row for Cast /Filters / info / Run / Close 
    """
    # filters for Desktop / Media
    with ui.row().classes('self-center'):

        await desktop_filters()

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
                    if str2bool(custom_config['system-stats']):
                        with ui.row().classes('self-center'):
                            frame_count = ui.number(prefix='F.').bind_value_from(CastAPI, 'total_frame')
                            frame_count.tooltip('TOTAL Frames')
                            frame_count.classes("w-20")
                            frame_count.props(remove='type=number', add='borderless')

                            total_reset_icon = ui.icon('restore')
                            total_reset_icon.style("cursor: pointer")
                            total_reset_icon.on('click', lambda: reset_total())

                            packet_count = ui.number(prefix='P.').bind_value_from(CastAPI, 'total_packet')
                            packet_count.tooltip('TOTAL DDP Packets')
                            packet_count.classes("w-20")
                            packet_count.props(remove='type=number', add='borderless')

                        ui.separator()

                        with ui.row().classes('self-center'):
                            cpu_count = ui.number(prefix='CPU%: ').bind_value_from(CastAPI, 'cpu')
                            cpu_count.classes("w-20")
                            cpu_count.props(remove='type=number', add='borderless')

                            ram_count = ui.number(prefix='RAM%: ').bind_value_from(CastAPI, 'ram')
                            ram_count.classes("w-20")
                            ram_count.props(remove='type=number', add='borderless')

                    if str2bool(custom_config['cpu-chart']):
                        await create_cpu_chart()

        await media_filters()

    ui.separator().classes('mt-6')

    """
    Log display
    """

    if str2bool(app_config['log_to_main']):
        with ui.expansion('Show log', icon='feed').classes('w-full'):
            log_ui = ui.log(max_lines=250).classes('w-full h-30')
            # logging Level
            logger.setLevel(app_config['log_level'].upper())
            # handler
            handler = LogElementHandler(log_ui)
            ui.context.client.on_connect(lambda: logger.addHandler(handler))
            ui.context.client.on_disconnect(lambda: logger.removeHandler(handler))
            # clear / load log file
            with ui.row().classes('w-full'):
                ui.button('Clear Log', on_click=lambda: log_ui.clear()).tooltip('Erase the log')
                dialog = ui.dialog().classes('w-full') \
                    .props(add='maximized transition-show="slide-up" transition-hide="slide-down"')
                with dialog, ui.card().classes('w-full'):
                    log_filename = 'log/WLEDVideoSync.log'
                    with open(log_filename) as file:
                        log_data = file.read()
                    ui.button('Close', on_click=dialog.close, color='red')
                    log_area = ui.textarea(value=log_data).classes('w-full').props(add='bg-color=blue-grey-4')
                    log_area.props(add="rows='25'")
                ui.button('See Log file', on_click=dialog.open).tooltip('Load log data from file')

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
        if sys.platform.lower() != 'win32':
            ui.button('shutdown', on_click=app.shutdown)
        with ui.row().classes('absolute inset-y-0 right-0.5 bg-red-900'):
            ui.link('® Zak-45 ' + str(datetime.now().strftime('%Y')), 'https://github.com/zak-45', new_tab=True) \
                .classes('text-white')
            ui.link('On-Line Help', 'https://github.com/zak-45/WLEDVideoSync', new_tab=True) \
                .tooltip('Go to documentation').classes('text-white')

    with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
        ui.button(on_click=footer.toggle).props('fab icon=contact_support')


@ui.page('/Manage')
async def main_page_cast_manage():
    """ Cast manage with full details page """

    ui.dark_mode(CastAPI.dark_mode)

    apply_custom()

    """
    Header with button menu
    """
    with ui.header(bordered=True, elevated=True).classes('items-center shadow-lg'):
        ui.label('Cast Manage').classes('text-white text-lg font-medium')
        ui.icon('video_settings')
        # Create buttons
        ui.button('MAIN', on_click=lambda: ui.navigate.to('/'), icon='home')
        ui.button('Desktop', on_click=lambda: ui.navigate.to('/Desktop'), icon='computer')
        ui.button('Media', on_click=lambda: ui.navigate.to('/Media'), icon='image')
        ui.button('API', on_click=lambda: ui.navigate.to('/docs', new_tab=True), icon='api')

    """
    Main tabs infos
    """
    await tabs_info_page()

    """
    Footer
    """
    with ui.footer():
        ui.button('Refresh Page', on_click=lambda: ui.navigate.to('/Manage'))

        await net_view_page()

        await media_dev_view_page()


@ui.page('/Player')
async def run_video_player_page():
    """
    timer created on video creation to refresh datas
    """
    if str2bool(custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)
    player_timer = ui.timer(int(app_config['timer']), callback=player_timer_action)
    await video_player_page()


async def video_player_page():
    """
    Video player
    """
    if str2bool(custom_config['animate-ui']):
        center_card_anim = Animate(ui.card, animation_name_in='fadeInUp', duration=1)
        center_card = center_card_anim.create_element()
    else:
        center_card = ui.card()

    center_card.classes('self-center w-2/3 bg-gray-500')
    with center_card:
        CastAPI.player = ui.video(app_config["video_file"]).classes('self-center')
        CastAPI.player.on('ended', lambda _: ui.notify('Video playback completed.'))
        CastAPI.player.on('timeupdate', lambda: get_player_time())
        CastAPI.player.on('durationchange', lambda: player_duration())
        CastAPI.player.set_visibility(True)
        with ui.row(wrap=False).classes('self-center'):
            ui.label() \
                .bind_text_from(Media, 'player_time') \
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
            media_frame = ui.knob(0, min=-1000, max=1000, step=1, show_value=True).classes('bg-gray') \
                .bind_value(Media, 'cast_skip_frames') \
                .tooltip('+ / - frames to CAST') \
                .bind_visibility_from(CastAPI.player)

            CastAPI.media_button_sync = ui.button('VSync', on_click=player_sync, color='green') \
                .tooltip('Sync Cast with Video Player Time') \
                .bind_visibility_from(CastAPI.player)

            media_reset_icon = ui.icon('restore')
            media_reset_icon.tooltip('sync Reset')
            media_reset_icon.style("cursor: pointer")
            media_reset_icon.on('click', lambda: reset_sync())
            media_reset_icon.bind_visibility_from(CastAPI.player)

            """ Refreshable """
            await sync_button()
            """ End Refresh """

            CastAPI.slider_button_sync = ui.button('TSync', on_click=slider_sync, color='green') \
                .tooltip('Sync Cast with Slider Time') \
                .bind_visibility_from(CastAPI.player)

            media_sync_delay = ui.knob(1, min=1, max=59, step=1, show_value=True).classes('bg-gray') \
                .bind_value(Media, 'auto_sync_delay') \
                .tooltip('Interval in sec to auto sync') \
                .bind_visibility_from(CastAPI.player)

            media_auto_sync = ui.checkbox('Auto Sync') \
                .bind_value(Media, 'auto_sync') \
                .tooltip('Auto Sync Cast with Time every x sec (based on interval set)') \
                .bind_visibility_from(CastAPI.player)

            media_all_sync_delay = ui.knob(1, min=-2000, max=2000, step=1, show_value=True).classes('bg-gray') \
                .bind_value(Media, 'add_all_sync_delay') \
                .tooltip('Add Delay in ms to all sync') \
                .bind_visibility_from(CastAPI.player)

            media_all_sync = ui.checkbox('Sync All') \
                .bind_value(Media,'all_sync') \
                .tooltip('Sync All Casts with selected time') \
                .bind_visibility_from(CastAPI.player)

        with ui.row().classes('self-center'):
            ui.icon('switch_video', color='blue', size='md') \
                .style("cursor: pointer") \
                .on('click', lambda visible=True: CastAPI.player.set_visibility(visible)) \
                .tooltip("Show Video player")

            hide_player = ui.icon('cancel_presentation', color='red', size='md') \
                .style("cursor: pointer") \
                .on('click', lambda visible=False: CastAPI.player.set_visibility(visible)) \
                .tooltip("Hide Video player")

            cast_player = ui.icon('cast', size='md') \
                .style("cursor: pointer") \
                .on('click', lambda: player_cast(CastAPI.player.source)) \
                .tooltip('Cast Video') \
                .bind_visibility_from(CastAPI.player)

            media_info = ui.icon('info', size='sd') \
                .style("cursor: pointer") \
                .on('click', lambda: player_media_info(CastAPI.player.source)) \
                .tooltip('Info') \
                .bind_visibility_from(CastAPI.player)

            video_file = ui.icon('folder', color='orange', size='md') \
                .style("cursor: pointer") \
                .on('click', player_pick_file) \
                .tooltip('Select audio / video file') \
                .bind_visibility_from(CastAPI.player)

            video_url = ui.input('Enter video Url / Path', placeholder='http://....') \
                .bind_visibility_from(CastAPI.player)
            video_url.tooltip('Enter Url, click on outside to validate the entry, '
                              ' hide and show player should refresh data')
            # video_url.on('keydown.enter', lambda: check_yt(video_url.value))
            video_url.on('focusout', lambda: check_yt(video_url.value))
            video_url_icon = ui.icon('published_with_changes')
            video_url_icon.style("cursor: pointer")
            video_url_icon.bind_visibility_from(CastAPI.player)
            # Progress bar
            CastAPI.progress_bar = ui.linear_progress(value=0, show_value=False)

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

    with ui.header():
        ui.label('Desktop').classes('text-lg font-medium')
        ui.icon('computer')
        ui.button('MAIN', on_click=lambda: ui.navigate.to('/'), icon='home')
        ui.button('Manage', on_click=lambda: ui.navigate.to('/Manage'), icon='video_settings')

    if str2bool(custom_config['animate-ui']):
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
        {'name': 'viformat', 'label': 'Method', 'field': 'viformat'}
    ]
    rows_c = [
        {'id': 0, 'viinput': Desktop.viinput, 'viformat': Desktop.viformat}
    ]
    columns_d = [
        {'name': 'vooutput', 'label': 'Output', 'field': 'vooutput', 'align': 'left'},
        {'name': 'voformat', 'label': 'Codec', 'field': 'voformat'}
    ]
    rows_d = [
        {'id': 0, 'vooutput': Desktop.vooutput, 'voformat': Desktop.voformat}
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
            await cast_icon(Desktop)
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

    if str2bool(custom_config['animate-ui']):
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
            ui.icon('restore_page', color='blue', size='sm') \
                .style('cursor: pointer').tooltip('Click to Validate/Refresh') \
                .on('click', lambda: ui.navigate.to('/Desktop'))

            with ui.card():
                new_rate = ui.number('FPS', value=Desktop.rate, min=1, max=60, precision=0)
                new_rate.bind_value_to(Desktop, 'rate', lambda value: int(value or 0))
                new_scale_width = ui.number('Scale Width', value=Desktop.scale_width, min=1, max=1920, precision=0)
                new_scale_width.bind_value_to(Desktop, 'scale_width', lambda value: int(value or 0))
                new_scale_height = (ui.number('Scale Height', value=Desktop.scale_height, min=1, max=1080, precision=0))
                new_scale_height.bind_value_to(Desktop, 'scale_height', lambda value: int(value or 0))

            with ui.card():
                new_wled = ui.input('wled', value=str(Desktop.wled))
                new_wled.bind_value_to(Desktop, 'wled', lambda value: str2bool(value))
                new_host = ui.input('IP', value=Desktop.host)
                new_host.on('focusout', lambda: update_attribute_by_name('Desktop', 'host', new_host.value))

            with ui.card():
                new_viinput = ui.input('Input', value=str(Desktop.viinput))
                new_viinput.on('focusout', lambda: update_attribute_by_name('Desktop', 'viinput', new_viinput.value))
                new_viformat = ui.input('Method', value=Desktop.viformat)
                new_viformat.bind_value_to(Desktop, 'viformat')
                ui.button('formats', on_click=display_formats)
                with ui.row():
                    ui.number('', value=Desktop.monitor_number, min=0, max=1).classes('w-10') \
                        .bind_value(Desktop, 'monitor_number') \
                        .tooltip('Enter monitor number')
                    ui.button('ScreenArea', on_click=select_sc_area) \
                        .tooltip('Select area from monitor')

            with ui.card():
                new_vooutput = ui.input('Output', value=str(Desktop.vooutput))
                new_vooutput.bind_value_to(Desktop, 'vooutput')
                new_voformat = ui.input('Codec', value=Desktop.voformat)
                new_voformat.bind_value_to(Desktop, 'voformat')
                ui.button('Codecs', on_click=display_codecs)

            with ui.card():
                new_put_to_buffer = ui.input('Capture Frame', value=str(Desktop.put_to_buffer))
                new_put_to_buffer.bind_value_to(Desktop, 'put_to_buffer', lambda value: str2bool(value))
                new_frame_max = ui.number('Number to Capture', value=Desktop.frame_max, min=1, max=30, precision=0)
                new_frame_max.tooltip('Max number of frame to capture')
                new_frame_max.bind_value_to(Desktop, 'frame_max', lambda value: int(value or 0))

            with ui.card():
                new_multicast = ui.input('Multicast', value=str(Desktop.multicast))
                new_multicast.bind_value_to(Desktop, 'multicast', lambda value: str2bool(value))
                new_cast_x = ui.number('Matrix X', value=Desktop.cast_x, min=0, max=1920, precision=0)
                new_cast_x.bind_value_to(Desktop, 'cast_x', lambda value: int(value or 0))
                new_cast_y = ui.number('Matrix Y', value=Desktop.cast_y, min=0, max=1080, precision=0)
                new_cast_y.bind_value_to(Desktop, 'cast_y', lambda value: int(value or 0))

            with ui.card():
                new_cast_devices = ui.input('Cast Devices', value=str(Desktop.cast_devices))
                new_cast_devices.on('focusout',
                                    lambda: update_attribute_by_name('Desktop', 'cast_devices', new_cast_devices.value))
                ui.button('Manage', on_click=lambda: cast_device_manage(Desktop))

    ui.separator().classes('mt-6')

    with ui.expansion('BUFFER', icon='grid_view', on_value_change=lambda: exp_edit_param.close()) \
            .classes('w-full'):
        if len(Desktop.frame_buffer) > 0:
            with ui.row():
                media_grid = ui.grid(columns=8)
                with media_grid:
                    for i in range(len(Desktop.frame_buffer)):
                        # put fixed size for preview
                        img = Utils.resize_image(Desktop.frame_buffer[i], 640, 360)
                        img = Image.fromarray(img)
                        await light_box_image(i, img, '', '', Desktop, 'frame_buffer')
                with ui.carousel(animated=True, arrows=True, navigation=True).props('height=480px'):
                    await generate_carousel(Desktop)

        else:
            with ui.card():
                ui.label('No image to show...').classes('animate-pulse')

    with ui.expansion('MULTICAST', icon='grid_view', on_value_change=lambda: exp_edit_param.close()) \
            .classes('w-full'):
        # columns number  = cast_x, number of cards = cast_x * cast_y
        if Desktop.multicast:
            with ui.row():
                await multi_preview(Desktop)
                await cast_devices_view(Desktop)
            if len(Desktop.cast_frame_buffer) > 0:
                with ui.grid(columns=Desktop.cast_x):
                    try:
                        for i in range(Desktop.cast_x * Desktop.cast_y):
                            # put fixed size for preview
                            img = Utils.resize_image(Desktop.cast_frame_buffer[i], 640, 360)
                            img = Image.fromarray(img)
                            await light_box_image(i, img, i, '', Desktop, 'cast_frame_buffer')
                    except Exception as error:
                        logger.error(traceback.format_exc())
                        logger.error(f'An exception occurred: {error}')
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

        with ui.dialog() as dialog, ui.card():
            win_title = Utils.windows_titles()
            editor = ui.json_editor({'content': {'json': win_title}}) \
                .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog.close, color='red')
        ui.button('Win TITLES', on_click=dialog.open, color='bg-red-800').tooltip('View windows titles')


@ui.page('/Media')
async def main_page_media():
    """
    Media param page
    """
    ui.dark_mode(CastAPI.dark_mode)

    apply_custom()

    with ui.header():
        ui.link('MEDIA', target='/Media').classes('text-white text-lg font-medium')
        ui.icon('image')
        ui.button('Main', on_click=lambda: ui.navigate.to('/'), icon='home')
        ui.button('Manage', on_click=lambda: ui.navigate.to('/Manage'), icon='video_settings')

    if str2bool(custom_config['animate-ui']):
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
            await cast_icon(Media)
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

    if str2bool(custom_config['animate-ui']):
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
            ui.icon('restore_page', color='blue', size='sm') \
                .style('cursor: pointer').tooltip('Click to Validate/Refresh') \
                .on('click', lambda: ui.navigate.to('/Media'))

            with ui.card():
                new_rate = ui.number('FPS', value=Media.rate, min=1, max=60, precision=0)
                new_rate.bind_value_to(Media, 'rate', lambda value: int(value or 0))
                new_scale_width = ui.number('Scale Width', value=Media.scale_width, min=1, max=1920, precision=0)
                new_scale_width.bind_value_to(Media, 'scale_width', lambda value: int(value or 0))
                new_scale_height = (ui.number('Scale Height', value=Media.scale_height, min=1, max=1080, precision=0))
                new_scale_height.bind_value_to(Media, 'scale_height', lambda value: int(value or 0))

            with ui.card():
                new_viinput = ui.input('Input', value=str(Media.viinput))
                new_viinput.on('focusout', lambda: update_attribute_by_name('Media', 'viinput', new_viinput.value))
                new_preview = ui.input('Preview', value=str(Media.preview))
                new_preview.bind_value_to(Media, 'preview', lambda value: str2bool(value))

            with ui.card():
                new_wled = ui.input('wled', value=str(Media.wled))
                new_wled.bind_value_to(Media, 'wled', lambda value: str2bool(value))
                new_host = ui.input('IP', value=Media.host)
                new_host.on('focusout', lambda: update_attribute_by_name('Media', 'host', new_host.value))

            with ui.card():
                new_put_to_buffer = ui.input('Capture Frame', value=str(Media.put_to_buffer))
                new_put_to_buffer.bind_value_to(Media, 'put_to_buffer', lambda value: str2bool(value))
                new_frame_max = ui.number('Number to Capture', value=Media.frame_max, min=1, max=30, precision=0)
                new_frame_max.tooltip('Max number of frame to capture')
                new_frame_max.bind_value_to(Media, 'frame_max', lambda value: int(value or 0))
                new_frame_index = ui.number('Seek to frame N°', value=Media.frame_index, min=0, precision=0)
                new_frame_index.bind_value_to(Media, 'frame_index', lambda value: int(value or 0))

            with ui.card():
                new_multicast = ui.input('Multicast', value=str(Media.multicast))
                new_multicast.bind_value_to(Media, 'multicast', lambda value: str2bool(value))
                new_cast_x = ui.number('Matrix X', value=Media.cast_x, min=0, max=1920, precision=0)
                new_cast_x.bind_value_to(Media, 'cast_x', lambda value: int(value or 0))
                new_cast_y = ui.number('Matrix Y', value=Media.cast_y, min=0, max=1080, precision=0)
                new_cast_y.bind_value_to(Media, 'cast_y', lambda value: int(value or 0))

            with ui.card():
                new_cast_devices = ui.input('Cast Devices', value=str(Media.cast_devices))
                new_cast_devices.on('focusout',
                                    lambda: update_attribute_by_name('Media', 'cast_devices', new_cast_devices.value))
                ui.button('Manage', on_click=lambda: cast_device_manage(Media))

    ui.separator().classes('mt-6')

    with ui.expansion('BUFFER', icon='grid_view', on_value_change=lambda: media_exp_edit_param.close()) \
            .classes('w-full'):
        if len(Media.frame_buffer) > 0:
            with ui.row():
                media_grid = ui.grid(columns=8)
                with media_grid:
                    for i in range(len(Media.frame_buffer)):
                        # put fixed size for preview
                        img = Utils.resize_image(Media.frame_buffer[i], 640, 360)
                        img = Image.fromarray(img)
                        await light_box_image(i, img, '', '', Media, 'frame_buffer')
                with ui.carousel(animated=True, arrows=True, navigation=True).props('height=480px'):
                    await generate_carousel(Media)

        else:
            with ui.card():
                ui.label('No image to show...').classes('animate-pulse')

    with ui.expansion('MULTICAST', icon='grid_view', on_value_change=lambda: media_exp_edit_param.close()) \
            .classes('w-full'):
        # columns number  = cast_x, number of cards = cast_x * cast_y
        if Media.multicast:
            with ui.row():
                await multi_preview(Media)
                await cast_devices_view(Media)
            if len(Media.cast_frame_buffer) > 0:
                with ui.grid(columns=Media.cast_x):
                    try:
                        for i in range(Media.cast_x * Media.cast_y):
                            # put fixed size for preview
                            img = Utils.resize_image(Media.cast_frame_buffer[i], 640, 360)
                            img = Image.fromarray(img)
                            await light_box_image(i, img, i, '', Media, 'cast_frame_buffer')
                    except Exception as error:
                        logger.error(traceback.format_exc())
                        logger.error(f'An exception occurred: {error}')
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
    main = ui.button('MAIN INTERFACE', on_click=lambda:(main.props('loading'), ui.navigate.to(f'/'))) \
        .classes('self-center')
    ui.button('API', on_click=lambda: ui.navigate.to(f'/docs')) \
        .classes('self-center')


@ui.page('/ws/docs')
async def ws_page():
    """
    websocket docs page
    :return:
    """
    ui.label('WEBSOCKETS Doc').classes('self-center')
    doc_txt = ui.textarea('WE endpoints').style('width: 50%')
    doc_txt.value = ('Use cast_image:x:z:f:d:r:c:i \n to send image number x (Media.buffer[x]) \n'
                     ' to cast device z (Media.cast_devices[z]) \n'
                     'image_number = int \n'
                     'device_number = int if -1 take host from Media\n'
                     'class_name = str (Desktop or Media) \n'
                     'fps_number = int max 60 \n'
                     'duration_number = int \n'
                     'retry_number = int if < 0 set to 0 \n'
                     'buffer_name = BUFFER or  MULTICAST \n'
                     'example: \n\n'
                     '{"action":'
                     '{"type":"cast_image", '
                     '"param":{"image_number":0,"device_number":-1, "class_name":"Media"}}}'
                     )


@ui.page('/info')
async def info_page():
    """ simple cast info page from systray """
    if str2bool(custom_config['animate-ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="./assets/css/animate.min.css"/>
        """)
    info_timer = ui.timer(int(app_config['timer']), callback=info_timer_action)
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


async def system_stats():
    CastAPI.cpu = psutil.cpu_percent(interval=1, percpu=False)
    CastAPI.ram = psutil.virtual_memory().percent
    CastAPI.total_packet = Desktop.total_packet + Media.total_packet
    CastAPI.total_frame = Desktop.total_frame + Media.total_frame

    if str2bool(custom_config['cpu-chart']):
        if CastAPI.cpu_chart is not None:
            now = datetime.now()
            date_time_str = now.strftime("%H:%M:%S")

            CastAPI.cpu_chart.options['series'][0]['data'].append(CastAPI.cpu)
            CastAPI.cpu_chart.options['xAxis']['data'].append(date_time_str)

            CastAPI.cpu_chart.update()

    if CastAPI.cpu >= 65:
        ui.notify('High CPU utilization', type='negative', close_button=True)
    if CastAPI.ram >= 95:
        ui.notify('High Memory utilization', type='negative', close_button=True)


@ui.refreshable
async def net_view_page():
    """
    Display network devices into the Json Editor
    :return:
    """
    with ui.dialog() as dialog, ui.card():
        editor = ui.json_editor({'content': {'json': Netdevice.http_devices}}) \
            .run_editor_method('updateProps', {'readOnly': True})
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('Net devices', on_click=dialog.open, color='bg-red-800').tooltip('View network devices')


@ui.refreshable
async def media_dev_view_page():
    """
    Display network devices into the Json Editor
    :return:
    """
    with ui.dialog() as dialog, ui.card():
        editor = ui.json_editor({'content': {'json': Utils.dev_list}}) \
            .run_editor_method('updateProps', {'readOnly': True})
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('Media devices', on_click=dialog.open, color='bg-red-800').tooltip('View Media devices')


"""
helpers /Commons
"""


async def sync_button():
    """ Sync Buttons """

    if Media.player_sync is True:
        # VSYNC
        CastAPI.media_button_sync.classes('animate-pulse')
        CastAPI.media_button_sync.props(add="color='gray'")
        if CastAPI.last_type_sync == 'player':
            CastAPI.media_button_sync.props(add="color='red'")
            CastAPI.media_button_sync.text = Media.player_time
        # TSYNC
        CastAPI.slider_button_sync.classes('animate-pulse')
        CastAPI.slider_button_sync.props(add="color='gray'")
        if CastAPI.last_type_sync == 'slider':
            CastAPI.slider_button_sync.props(add="color='red'")
            CastAPI.slider_button_sync.text = Media.player_time

    elif Media.player_sync is False and CastAPI.type_sync != 'none':
        CastAPI.media_button_sync.props(add="color=green")
        CastAPI.media_button_sync.classes(remove="animate-pulse")
        CastAPI.media_button_sync.text = "VSYNC"
        CastAPI.media_button_sync.update()
        CastAPI.slider_button_sync.props(add="color=green")
        CastAPI.slider_button_sync.classes(remove="animate-pulse")
        CastAPI.slider_button_sync.text = "TSYNC"
        CastAPI.slider_button_sync.update()
        CastAPI.type_sync = 'none'


async def cast_manage():
    """
    refresh cast parameters  on the root page '/'
    :return:
    """

    if Desktop.count > 0:
        CastAPI.desktop_cast.props(add="color=red")
        CastAPI.desktop_cast.classes(add="animate-pulse")
    elif Desktop.stopcast is True:
        CastAPI.desktop_cast.props(add="color=yellow")
        CastAPI.desktop_cast_run.set_visibility(False)
        CastAPI.desktop_cast.classes(remove="animate-pulse")
    else:
        CastAPI.desktop_cast.props(add="color=green")
        CastAPI.desktop_cast.classes(remove="animate-pulse")
    if Desktop.stopcast is False:
        CastAPI.desktop_cast_run.set_visibility(True)

    if Media.count > 0:
        CastAPI.media_cast.props(add="color=red")
        CastAPI.media_cast.classes(add="animate-pulse")
    elif Media.stopcast is True:
        CastAPI.media_cast.props(add="color=yellow")
        CastAPI.media_cast.classes(remove="animate-pulse")
        CastAPI.media_cast_run.set_visibility(False)
    else:
        CastAPI.media_cast.props(add="color=green")
        CastAPI.media_cast.classes(remove="animate-pulse")
    if Media.stopcast is False:
        CastAPI.media_cast_run.set_visibility(True)


async def cast_icon(class_obj):
    """
    refresh Icon color on '/Desktop' and '/Media' pages
    :param class_obj:
    :return:
    """

    def upd_value():
        class_obj.stopcast = False
        my_icon.classes(remove='animate-pulse')
        ui.notify('Cast allowed', position='center', close_button=True, type='positive')

    cast_col = 'green' if class_obj.stopcast is False else 'yellow'
    my_icon = ui.icon('cast_connected', size='sm', color=cast_col) \
        .style('cursor: pointer') \
        .tooltip('Click to authorize') \
        .on('click', lambda: (my_icon.props(add='color=green'), upd_value())) \
        .classes('animate-pulse')


async def media_filters():
    #  Filters for Media
    with ui.card().classes('text-sm shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700'):
        ui.label('Filters/Effects Media')
        with ui.row().classes('w-44'):
            ui.checkbox('Flip') \
                .bind_value(Media, 'flip') \
                .classes('w-20')
            ui.number('type', min=0, max=1) \
                .bind_value(Media, 'flip_vh', forward=lambda value: int(value or 0)) \
                .classes('w-20')
            ui.number('W').classes('w-20').bind_value(Media, 'scale_width', forward=lambda value: int(value or 0))
            ui.number('H').classes('w-20').bind_value(Media, 'scale_height', forward=lambda value: int(value or 0))
            with ui.row().classes('w-44').style('justify-content: flex-end'):
                ui.label('gamma')
                ui.slider(min=0.01, max=4, step=0.01) \
                    .props('label-always') \
                    .bind_value(Media, 'gamma')
            with ui.column(wrap=True):
                with ui.row():
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-red') \
                            .bind_value(Media, 'balance_r')
                        ui.label('R').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-green') \
                            .bind_value(Media, 'balance_g')
                        ui.label('G').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-blue') \
                            .bind_value(Media, 'balance_b')
                        ui.label('B').classes('self-center')
                ui.button('reset', on_click=lambda: reset_rgb('Media')).classes('self-center')

    with ui.card().classes('text-sm shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]'):
        with ui.row().classes('w-20').style('justify-content: flex-end'):
            ui.label('saturation')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Media, 'saturation')
            ui.label('brightness').classes('text-right')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Media, 'brightness')
            ui.label('contrast')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Media, 'contrast')
            ui.label('sharpen')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Media, 'sharpen')
            ui.checkbox('auto') \
                .bind_value(Media, 'auto_bright', forward=lambda value: value) \
                .tooltip('Auto bri/contrast')
            ui.slider(min=0, max=100, step=1) \
                .props('label-always') \
                .bind_value(Media, 'clip_hist_percent')


async def desktop_filters():
    """ desktop filter page creation"""

    with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700'):
        ui.label('Filters/Effects Desktop')
        with ui.row().classes('w-44'):
            ui.checkbox('Flip') \
                .bind_value(Desktop, 'flip') \
                .classes('w-20')
            ui.number('type', min=0, max=1) \
                .bind_value(Desktop, 'flip_vh', forward=lambda value: int(value or 0)) \
                .classes('w-20')
            ui.number('W').classes('w-20').bind_value(Desktop, 'scale_width', forward=lambda value: int(value or 0))
            ui.number('H').classes('w-20').bind_value(Desktop, 'scale_height',
                                                      forward=lambda value: int(value or 0))
            with ui.row().classes('w-44').style('justify-content: flex-end'):
                ui.label('gamma')
                ui.slider(min=0.01, max=4, step=0.01) \
                    .props('label-always') \
                    .bind_value(Desktop, 'gamma')
            with ui.column(wrap=True):
                with ui.row():
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-red') \
                            .bind_value(Desktop, 'balance_r')
                        ui.label('R').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-green') \
                            .bind_value(Desktop, 'balance_g')
                        ui.label('G').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-blue') \
                            .bind_value(Desktop, 'balance_b')
                        ui.label('B').classes('self-center')
                ui.button('reset', on_click=lambda: reset_rgb('Desktop')).classes('self-center')

    with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]'):
        with ui.row().classes('w-20').style('justify-content: flex-end'):
            ui.label('saturation')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Desktop, 'saturation')
            ui.label('brightness')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Desktop, 'brightness')
            ui.label('contrast')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Desktop, 'contrast')
            ui.label('sharpen')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Desktop, 'sharpen')
            ui.checkbox('auto') \
                .bind_value(Desktop, 'auto_bright', forward=lambda value: value) \
                .tooltip('Auto bri/contrast')
            ui.slider(min=0, max=100, step=1) \
                .props('label-always') \
                .bind_value(Desktop, 'clip_hist_percent')


async def youtube_search():
    """
    display search result from pytube
    """

    if str2bool(custom_config['animate-ui']):
        animated_yt_area = Animate(ui.scroll_area, animation_name_in="backInDown", duration=1.5)
        yt_area = animated_yt_area.create_element()
    else:
        yt_area = ui.scroll_area()

    yt_area.bind_visibility_from(CastAPI.player)
    yt_area.classes('w-full border')
    CastAPI.search_areas.append(yt_area)
    with yt_area:
        YtSearch()


async def youtube_clear_search():
    """
    Clear search results
    """

    for area in CastAPI.search_areas:
        try:
            if str2bool(custom_config['animate-ui']):
                animated_area = Animate(area, animation_name_out="backOutUp", duration=1)
                animated_area.delete_element(area)
            else:
                area.delete()
        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'Search area does not exist: {error}')
    CastAPI.search_areas = []


async def reset_total():
    """ reset frames / packets total values for Media and Desktop """
    Media.reset_total = True
    Desktop.reset_total = True
    #  instruct first cast to reset values
    if len(Media.cast_names) != 0:
        result = await action_to_thread(class_name='Media',
                                        cast_name=Media.cast_names[0],
                                        action='reset',
                                        clear=False,
                                        execute=True
                                        )
        ui.notify(result)

    if len(Desktop.cast_names) != 0:
        result = await action_to_thread(class_name='Desktop',
                                        cast_name=Desktop.cast_names[0],
                                        action='reset',
                                        clear=False,
                                        execute=True
                                        )
        ui.notify(result)

    ui.notify('Reset Total')


async def create_cpu_chart():
    CastAPI.cpu_chart = ui.echart({
        'darkMode': 'auto',
        'legend': {
            'show': 'true',
            'data': []
        },
        'textStyle': {
            'fontSize': 1,
            'color': '#d2a'
        },
        'grid': {
            'top': 60
        },
        'tooltip': {
            'trigger': 'axis'
        },
        'xAxis': {
            'type': 'category',
            'data': []
        },
        'yAxis': {
            'type': 'value'
        },
        'series': [{
            'data': [],
            'name': 'CPU %',
            'areaStyle': {'color': '#535894', 'opacity': 0.5},
            'type': 'line'
        }]
    }).style('height:80px ')


def select_sc_area():
    """ Draw rectangle to monitor x """
    monitor = int(Desktop.monitor_number)
    thread = threading.Thread(target=Sa.run, args=(monitor,))
    thread.daemon = True
    thread.start()
    thread.join()
    # For Calculate crop parameters
    Desktop.screen_coordinates = Sa.screen_coordinates
    #
    logger.info(f'Monitor infos: {Sa.monitors}')
    logger.info(f'Area Coordinates: {Sa.coordinates} from monitor {monitor}')
    logger.info(f'Area screen Coordinates: {Sa.screen_coordinates} from monitor {monitor}')


async def slider_sync():
    """ Set Sync Cast to True """
    current_time = CastAPI.video_slider.value
    ui.notify(f'Slider Time : {current_time}')
    Media.player_time = current_time * 1000
    Media.player_sync = True
    CastAPI.type_sync = 'slider'
    CastAPI.last_type_sync = 'slider'
    CastAPI.slider_button_sync.props(add="color=red")
    CastAPI.slider_button_sync.text = round(current_time)
    CastAPI.slider_button_sync.classes('animate-pulse')
    CastAPI.media_button_sync.props(remove="color=red")
    CastAPI.media_button_sync.text = "VSYNC"


def slider_time(current_time):
    """ Set player time for Cast """
    if current_time > 0:
        Media.player_time = current_time * 1000


async def reset_sync():
    Media.player_sync = False
    ui.notify('Reset Sync')


async def player_sync():
    """ Set Sync cast to True """
    await context.client.connected()
    current_time = await ui.run_javascript("document.querySelector('video').currentTime", timeout=2)
    ui.notify(f'Player Time : {current_time}')
    Media.player_time = current_time * 1000
    Media.player_sync = True
    CastAPI.type_sync = 'player'
    CastAPI.last_type_sync = 'player'
    CastAPI.media_button_sync.props(add="color=red")
    CastAPI.media_button_sync.text = round(current_time)
    CastAPI.media_button_sync.classes('animate-pulse')
    CastAPI.slider_button_sync.props(remove="color=red")
    CastAPI.slider_button_sync.text = "TSYNC"


async def get_player_time():
    """
    Retrieve current play time from the Player
    Set player time for Cast to Sync
    """
    await context.client.connected()
    if CastAPI.type_sync == 'player' or CastAPI.last_type_sync == 'player':
        current_time = await ui.run_javascript("document.querySelector('video').currentTime", timeout=2)
        Media.player_time = round(current_time * 1000)


async def player_duration():
    """
    Return current duration time from the Player
    Set slider max value to video duration
    """
    await context.client.connected()
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


def dev_stats_info_page():
    """ devices charts """

    dev_ip = ['--dev_ip']
    ips_list = []
    if Desktop.host != '127.0.0.1':
        ips_list.append(Desktop.host)
    if Media.host != '127.0.0.1':
        ips_list.append(Media.host)

    for i in range(len(Desktop.cast_devices)):
        cast_ip = Desktop.cast_devices[i][1]
        ips_list.append(cast_ip)

    for i in range(len(Media.cast_devices)):
        cast_ip = Media.cast_devices[i][1]
        ips_list.append(cast_ip)

    if len(ips_list) == 0:
        ips_list.append('127.0.0.1')

    ips_list = [','.join(ips_list)]

    dark = []
    if CastAPI.dark_mode is True:
        dark = ['--dark']

    # run chart on its own process
    Popen(["devstats"] + dev_ip + ips_list + dark,
          executable=select_chart_exe())

    logger.info('Run Device(s) Charts')
    CastAPI.charts_row.set_visibility(False)


def net_stats_info_page():
    """ network charts """

    dark = []
    if CastAPI.dark_mode is True:
        dark = ['--dark']

    Popen(["netstats"] + dark,
          executable=select_chart_exe())

    CastAPI.charts_row.set_visibility(False)
    logger.info('Run Network Chart')


def sys_stats_info_page():
    """ system charts """

    dark = []
    if CastAPI.dark_mode is True:
        dark = ['--dark']

    Popen(["sysstats"] + dark,
          executable=select_chart_exe())

    CastAPI.charts_row.set_visibility(False)
    logger.info('Run System Charts')


def select_chart_exe():
    return app_config['charts_exe']


async def player_media_info(player_media):
    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.get_media_info(player_media)}}) \
            .run_editor_method('updateProps', {'readOnly': True, 'mode': 'table'})


async def display_formats():
    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.list_formats()}}) \
            .run_editor_method('updateProps', {'readOnly': True})


async def display_codecs():
    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.list_codecs()}}) \
            .run_editor_method('updateProps', {'readOnly': True})


"""
Filter preset mgr
"""


def manage_filter_presets(class_name):
    """ Manage presets"""
    ui.button('save preset', on_click=lambda: save_filter_preset(class_name)).classes('w-20')
    ui.button('load preset', on_click=lambda: load_filter_preset(class_name)).classes('w-20')


async def save_filter_preset(class_name):
    """ save preset to ini file """

    def save_file(f_name):

        if f_name == ' ' or f_name is None or f_name == '':
            ui.notification(f'Preset name could not be blank :  {f_name}', type='negative')

        else:
            f_name = f'./config/presets/filter/{class_name}/' + f_name + '.ini'
            if os.path.isfile(f_name):
                ui.notification(f'Preset {f_name} already exist ', type='warning')

            else:
                class_obj = globals()[class_name]
                preset = configparser.ConfigParser()

                preset['RGB'] = {}
                preset['RGB']['balance_r'] = str(class_obj.balance_r)
                preset['RGB']['balance_g'] = str(class_obj.balance_g)
                preset['RGB']['balance_b'] = str(class_obj.balance_b)
                preset['SCALE'] = {}
                preset['SCALE']['scale_width'] = str(class_obj.scale_width)
                preset['SCALE']['scale_height'] = str(class_obj.scale_height)
                preset['FLIP'] = {}
                preset['FLIP']['flip'] = str(class_obj.flip)
                preset['FLIP']['flip_vh'] = str(class_obj.flip_vh)
                preset['FILTERS'] = {}
                preset['FILTERS']['saturation'] = str(class_obj.saturation)
                preset['FILTERS']['brightness'] = str(class_obj.brightness)
                preset['FILTERS']['contrast'] = str(class_obj.contrast)
                preset['FILTERS']['sharpen'] = str(class_obj.sharpen)
                preset['AUTO'] = {}
                preset['AUTO']['auto_bright'] = str(class_obj.auto_bright)
                preset['AUTO']['clip_hist_percent'] = str(class_obj.clip_hist_percent)
                preset['GAMMA'] = {}
                preset['GAMMA']['gamma'] = str(class_obj.gamma)

                with open(f_name, 'w') as configfile:  # save
                    preset.write(configfile)

                dialog.close()
                ui.notification(f'Preset saved for {class_name} as {f_name}')

    with ui.dialog() as dialog:
        dialog.open()
        with ui.card():
            ui.label(class_name).classes('self-center')
            ui.separator()
            file_name = ui.input('Enter name', placeholder='preset name')
            with ui.row():
                ui.button('OK', on_click=lambda: save_file(file_name.value))
                ui.button('Cancel', on_click=dialog.close)


async def load_filter_preset(class_name, interactive=True, file_name=None):
    """ load a preset """

    if class_name not in ['Desktop', 'Media']:
        logger.error(f'Unknown Class Name : {class_name}')
        return False

    def apply_preset():
        try:
            class_obj = globals()[class_name]
            class_obj.balance_r = int(preset_rgb['balance_r'])
            class_obj.balance_g = int(preset_rgb['balance_g'])
            class_obj.balance_b = int(preset_rgb['balance_b'])
            class_obj.flip = str2bool(preset_flip['flip'])
            class_obj.flip_vh = int(preset_flip['flip_vh'])
            class_obj.scale_width = int(preset_scale['scale_width'])
            class_obj.scale_height = int(preset_scale['scale_height'])
            class_obj.saturation = int(preset_filters['saturation'])
            class_obj.brightness = int(preset_filters['brightness'])
            class_obj.contrast = int(preset_filters['contrast'])
            class_obj.sharpen = int(preset_filters['sharpen'])
            class_obj.auto_bright = str2bool(preset_auto['auto_bright'])
            class_obj.clip_hist_percent = int(preset_auto['clip_hist_percent'])
            class_obj.gamma = float(preset_gamma['gamma'])
            ui.notify('Preset applied', type='info')

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'Error to apply preset : {error}')
            ui.notify('Error to apply Preset', type='negative', position='center')

    if interactive:
        with ui.dialog() as dialog:
            dialog.open()
            with ui.card().classes('self-center'):
                ui.label(class_name).classes('self-center')
                ui.separator()
                ui.button('EXIT', on_click=dialog.close)
                result = await LocalFilePicker(f'config/presets/filter/{class_name}', multiple=False)
                editor_data = {}
                if result is not None:
                    preset_config_r = cfg.load(result[0])
                    preset_rgb = preset_config_r.get('RGB')
                    editor_data.update(preset_rgb)
                    preset_flip = preset_config_r.get('FLIP')
                    editor_data.update(preset_flip)
                    preset_scale = preset_config_r.get('SCALE')
                    editor_data.update(preset_scale)
                    preset_filters = preset_config_r.get('FILTERS')
                    editor_data.update(preset_filters)
                    preset_auto = preset_config_r.get('AUTO')
                    editor_data.update(preset_auto)
                    preset_gamma = preset_config_r.get('GAMMA')
                    editor_data.update(preset_gamma)

                    with ui.expansion('See values'):
                        editor = ui.json_editor({'content': {'json': editor_data}}) \
                            .run_editor_method('updateProps', {'readOnly': True})

                    with ui.row():
                        ui.button('OK', on_click=apply_preset)
                else:
                    preset_config_r = 'None'
                ui.label(f'Preset to apply: {preset_config_r}')
    else:
        preset_config_r = cfg.load(f'config/presets/filter/{class_name}/' + file_name)
        preset_rgb = preset_config_r.get('RGB')
        preset_flip = preset_config_r.get('FLIP')
        preset_scale = preset_config_r.get('SCALE')
        preset_filters = preset_config_r.get('FILTERS')
        preset_auto = preset_config_r.get('AUTO')
        preset_gamma = preset_config_r.get('GAMMA')
        apply_preset()


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


async def save_cast_preset(class_name):
    """ save preset to ini file """

    def save_file(f_name):

        if f_name == ' ' or f_name is None or f_name == '':
            ui.notification(f'Preset name could not be blank :  {f_name}', type='negative')

        else:
            f_name = f'./config/presets/cast/{class_name}/' + f_name + '.ini'
            if os.path.isfile(f_name):
                ui.notification(f'Preset {f_name} already exist ', type='warning')

            else:

                class_obj = globals()[class_name]
                preset = configparser.ConfigParser()

                preset['GENERAL'] = {}
                preset['GENERAL']['rate'] = str(class_obj.rate)
                preset['GENERAL']['stopcast'] = str(class_obj.stopcast)
                preset['GENERAL']['scale_width'] = str(class_obj.scale_width)
                preset['GENERAL']['scale_height'] = str(class_obj.scale_height)
                preset['GENERAL']['wled'] = str(class_obj.wled)
                preset['GENERAL']['wled_live'] = str(class_obj.wled_live)
                preset['GENERAL']['host'] = str(class_obj.host)
                preset['GENERAL']['viinput'] = str(class_obj.viinput)
                preset['MULTICAST'] = {}
                preset['MULTICAST']['multicast'] = str(class_obj.multicast)
                preset['MULTICAST']['cast_x'] = str(class_obj.cast_x)
                preset['MULTICAST']['cast_y'] = str(class_obj.cast_y)
                preset['MULTICAST']['cast_devices'] = str(class_obj.cast_devices)

                with open(f_name, 'w') as configfile:  # save
                    preset.write(configfile)

                dialog.close()
                ui.notification(f'Preset saved for {class_name} as {f_name}')

    with ui.dialog() as dialog:
        dialog.open()
        with ui.card():
            ui.label(class_name).classes('self-center')
            ui.separator()
            file_name = ui.input('Enter name', placeholder='preset name')

            with ui.row():
                ui.button('OK', on_click=lambda: save_file(file_name.value))
                ui.button('Cancel', on_click=dialog.close)


async def load_cast_preset(class_name, interactive=True, file_name=None):
    """ load a preset """

    if class_name not in ['Desktop', 'Media']:
        logger.error(f'Unknown Class Name : {class_name}')
        return False

    def apply_preset():
        try:
            class_obj = globals()[class_name]
            class_obj.rate = int(preset_general['rate'])
            class_obj.stopcast = str2bool(preset_general['stopcast'])
            class_obj.scale_width = int(preset_general['scale_width'])
            class_obj.scale_height = int(preset_general['scale_height'])
            class_obj.wled = str2bool(preset_general['wled'])
            class_obj.wled_live = str2bool(preset_general['wled_live'])
            class_obj.host = preset_general['host']

            try:
                viinput = int(preset_general['viinput'])
            except ValueError:
                viinput = str(preset_general['viinput'])

            class_obj.viinput = viinput

            class_obj.multicast = str2bool(preset_multicast['multicast'])
            class_obj.cast_x = int(preset_multicast['cast_x'])
            class_obj.cast_y = int(preset_multicast['cast_y'])
            class_obj.cast_devices = eval(preset_multicast['cast_devices'])
            ui.notify('Preset applied', type='info')

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'Error to apply preset : {error}')
            ui.notify('Error to apply Preset', type='negative', position='center')

    if interactive:
        with ui.dialog() as dialog:
            dialog.open()
            with ui.card().classes('self-center'):
                ui.label(class_name).classes('self-center')
                ui.separator()
                ui.button('EXIT', on_click=dialog.close)
                result = await LocalFilePicker(f'config/presets/cast/{class_name}', multiple=False)
                if result is not None:
                    editor_data = {}
                    preset_config_r = cfg.load(result[0])
                    preset_general = preset_config_r.get('GENERAL')
                    editor_data.update(preset_general)
                    preset_multicast = preset_config_r.get('MULTICAST')
                    editor_data.update(preset_multicast)

                    with ui.expansion('See values'):
                        editor = ui.json_editor({'content': {'json': editor_data}}) \
                            .run_editor_method('updateProps', {'readOnly': True})

                    with ui.row():
                        ui.button('OK', on_click=apply_preset)
                else:
                    preset_config_r = 'None'
                ui.label(f'Preset to apply: {preset_config_r}')
    else:
        preset_config_r = cfg.load(f'config/presets/cast/{class_name}/' + file_name)
        preset_general = preset_config_r.get('GENERAL')
        preset_multicast = preset_config_r.get('MULTICAST')
        apply_preset()


"""
END Cast preset mgr
"""


async def player_cast(source):
    """ Cast from video CastAPI.player only for Media"""
    # await context.client.connected()
    media_info = Utils.get_media_info(source)
    if Media.stopcast:
        ui.notify(f'Cast NOT allowed to run from : {source}', type='warning')
    else:
        Media.viinput = source
        Media.rate = int(round(float(media_info[3].split(':')[1].replace(' ', '').replace('"', ''))))
        ui.notify(f'Cast running from : {source}')
        Media.cast(shared_buffer=t_data_buffer)
    CastAPI.player.play()


async def cast_device_manage(class_name):
    with ui.dialog() as dialog, ui.card().classes('w-1/2'):
        dialog.open()
        columns = [
            {'field': 'number', 'editable': True, 'sortable': True, 'checkboxSelection': True},
            {'field': 'ip', 'editable': True},
            {'field': 'id', 'hide': True},
        ]
        rows = [
        ]

        def handle_cell_value_change(e):
            new_row = e.args['data']
            ui.notify(f'Updated row to: {e.args["data"]}')
            rows[:] = [row | new_row if row['id'] == new_row['id'] else row for row in rows]

        aggrid = ui.aggrid({
            'columnDefs': columns,
            'rowData': rows,
            'rowSelection': 'multiple',
            'stopEditingWhenCellsLoseFocus': True,
        }).on('cellValueChanged', handle_cell_value_change)

        def add_row():
            row_new_id = max((dx['id'] for dx in rows), default=-1) + 1
            rows.append({'number': 0, 'ip': '127.0.0.1', 'id': row_new_id})
            aggrid.update()

        def add_net():
            i = len(class_name.cast_devices)
            for net in Netdevice.http_devices:
                i += 1
                row_new_id = max((dx['id'] for dx in rows), default=-1) + 1
                rows.append({'number': i, 'ip': Netdevice.http_devices[net]['address'], 'id': row_new_id})
                aggrid.update()

        async def update_cast_devices():
            new_cast_devices = []
            for row in await aggrid.get_selected_rows():
                new_cast_device = tuple((row["number"], row["ip"]))
                new_cast_devices.append(new_cast_device)
            sorted_devices = sorted(new_cast_devices, key=lambda x: x[0])
            class_name.cast_devices.clear()
            class_name.cast_devices.extend(sorted_devices)
            dialog.close()
            ui.notify('New data entered into cast_devices, click on validate/refresh to see them ')

        for item in class_name.cast_devices:
            new_id = max((dx['id'] for dx in rows), default=-1) + 1
            rows.append({'number': item[0], 'ip': item[1], 'id': new_id})

        with ui.row():
            ui.button('Add row', on_click=add_row)
            ui.button('Add Net', on_click=add_net)
            ui.button('Select all', on_click=lambda: aggrid.run_grid_method('selectAll'))
            ui.button('Validate', on_click=lambda: update_cast_devices())
            ui.button('Close', color='red', on_click=lambda: dialog.close())


def reset_rgb(class_name):
    """ reset RGB value """

    class_obj = globals()[class_name]
    class_obj.balance_r = 0
    class_obj.balance_g = 0
    class_obj.balance_b = 0


async def cast_manage_page():
    """
    Cast parameters on the root page '/'
    :return:
    """

    with ui.card().tight().classes('self-center'):
        with ui.row():
            with ui.column(wrap=True):
                if Desktop.count > 0:
                    my_col = 'red'
                elif Desktop.stopcast:
                    my_col = 'yellow'
                else:
                    my_col = 'green'
                CastAPI.desktop_cast = ui.icon('cast', size='xl', color=my_col)
                CastAPI.desktop_cast_run = ui.button(icon='touch_app', on_click=lambda: init_cast(Desktop, log_ui)) \
                    .classes('shadow-lg') \
                    .tooltip('Initiate Desktop Cast')
                if Desktop.stopcast is True:
                    CastAPI.desktop_cast_run.set_visibility(False)

            ui.icon('stop_screen_share', size='xs', color='red') \
                .style('cursor: pointer') \
                .on('click', lambda: cast_stop(Desktop)).tooltip('Stop Cast')

            if str2bool(custom_config['animate-ui']):
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

            with ui.column(wrap=True):
                if Media.count > 0:
                    my_col = 'red'
                elif Media.stopcast:
                    my_col = 'yellow'
                else:
                    my_col = 'green'
                CastAPI.media_cast = ui.icon('cast', size='xl', color=my_col)
                CastAPI.media_cast_run = ui.button(icon='touch_app', on_click=lambda: init_cast(Media, log_ui)) \
                    .classes('shadow-lg') \
                    .tooltip('Initiate Media Cast')
                if Media.stopcast is True:
                    CastAPI.media_cast_run.set_visibility(False)


async def tabs_info_page():
    # grab data
    info_data = util_casts_info()
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

    if str2bool(custom_config['animate-ui']):
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
    with (ui.tab_panels(tabs, value=p_desktop).classes('w-full')):
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
                    casts_row = ui.row()
                    with casts_row:
                        for item in desktop_threads:
                            item_exp = ui.expansion(item, icon='cast') \
                                .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')
                            with item_exp:
                                with ui.row():
                                    ui.button(icon='delete_forever',
                                              on_click=lambda item=item, item_exp=item_exp: action_to_casts(
                                                  class_name='Desktop',
                                                  cast_name=item,
                                                  action='stop',
                                                  clear=False,
                                                  execute=True,
                                                  exp_item=item_exp)
                                              ).classes('shadow-lg').tooltip('Cancel Cast')
                                    ui.button(icon='add_photo_alternate',
                                              on_click=lambda item=item: action_to_casts(class_name='Desktop',
                                                                                         cast_name=item,
                                                                                         action='shot',
                                                                                         clear=False,
                                                                                         execute=True)
                                              ).classes('shadow-lg').tooltip('Capture picture')
                                    if info_data[item]["data"]["preview"]:
                                        ui.button(icon='cancel_presentation',
                                                  on_click=lambda item=item: action_to_casts(class_name='Desktop',
                                                                                             cast_name=item,
                                                                                             action='close_preview',
                                                                                             clear=False,
                                                                                             execute=True)
                                                  ).classes('shadow-lg').tooltip('Stop Preview')

                                editor = ui.json_editor({'content': {'json': info_data[item]["data"]}}) \
                                    .run_editor_method('updateProps', {'readOnly': True})

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
                    with ui.row():
                        for item in media_threads:
                            item_exp = ui.expansion(item, icon='cast') \
                                .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')
                            with item_exp:
                                with ui.row():
                                    ui.button(icon='delete_forever',
                                              on_click=lambda item=item, item_exp=item_exp: action_to_casts(
                                                  class_name='Media',
                                                  cast_name=item,
                                                  action='stop',
                                                  clear=False,
                                                  execute=True,
                                                  exp_item=item_exp)
                                              ).classes('shadow-lg').tooltip('Cancel Cast')
                                    ui.button(icon='add_photo_alternate',
                                              on_click=lambda item=item: action_to_casts(class_name='Media',
                                                                                         cast_name=item,
                                                                                         action='shot',
                                                                                         clear=False,
                                                                                         execute=True)) \
                                        .classes('shadow-lg').tooltip('Capture picture')
                                    if info_data[item]["data"]["preview"]:
                                        ui.button(icon='cancel_presentation',
                                                  on_click=lambda item=item:
                                                  action_to_casts(class_name='Media',
                                                                  cast_name=item,
                                                                  action='close_preview',
                                                                  clear=False,
                                                                  execute=True)) \
                                            .classes('shadow-lg').tooltip('Stop Preview')

                                editor = ui.json_editor({'content': {'json': info_data[item]["data"]}}) \
                                    .run_editor_method('updateProps', {'readOnly': True})


async def action_to_casts(class_name, cast_name, action, clear, execute, exp_item=None):
    await action_to_thread(class_name, cast_name, action, clear, execute)
    if action == 'stop':
        exp_item.close()
        ui.notification(f'Stopping {cast_name}...', type='warning', position='center', timeout=1)
        exp_item.delete()
    elif action == 'shot':
        ui.notification(f'Saving image to buffer for  {cast_name}...', type='positive', timeout=1)
    elif action == 'close_preview':
        ui.notification(f'Preview window terminated for  {cast_name}...', type='info', timeout=1)


async def show_thread_info():
    dialog = ui.dialog().props(add='transition-show="slide-down" transition-hide="slide-up"')
    with dialog, ui.card():
        cast_info = util_casts_info()
        editor = ui.json_editor({'content': {'json': cast_info}}) \
            .run_editor_method('updateProps', {'readOnly': True})
        ui.button('Close', on_click=dialog.close, color='red')
        dialog.open()


async def root_timer_action():
    """
    timer action occur only when root page is active '/'
    :return:
    """

    await sync_button()

    await cast_manage()

    if str2bool(custom_config['system-stats']):
        await system_stats()


async def info_timer_action():
    """
    timer action occur only when info page is active '/info'
    :return:
    """

    await cast_manage()


async def player_timer_action():
    """
    timer action occur when player is displayed
    :return:
    """
    await sync_button()


async def generate_carousel(class_obj):
    """ Images carousel for Desktop and Media """

    for i in range(len(class_obj.frame_buffer)):
        with ui.carousel_slide().classes('-p0'):
            carousel_image = Image.fromarray(class_obj.frame_buffer[i])
            h, w = class_obj.frame_buffer[i].shape[:2]
            img = ui.interactive_image(carousel_image.resize(size=(640, 360))).classes('w-[640]')
            with img:
                ui.button(text=str(i) + ':size:' + str(w) + 'x' + str(h), icon='tag') \
                    .props('flat fab color=white') \
                    .classes('absolute top-0 left-0 m-2') \
                    .tooltip('Image Number')


async def cast_to_wled(class_obj, image_number):
    """
    Cast to wled from GUI
    used on the buffer images
    """

    if not class_obj.wled:
        ui.notify('No WLED device', type='negative', position='center')
        return

    is_alive = Utils.check_ip_alive(class_obj.host)

    # check if valid wled device
    if not is_alive:
        logger.warning('Device do not accept connection to port 80')
        ui.notify('Device do not accept connection to port 80', type='warning')
    else:
        ui.notify(f'Cast to device : {class_obj.host}')
        if class_obj.__module__ == 'desktop':
            class_name = 'Desktop'
        elif class_obj.__module__ == 'media':
            class_name = 'Media'
        else:
            class_name = 'unknown'

        # select buffer for image to send
        if class_obj.multicast:
            buffer_name = 'multicast'
        else:
            buffer_name = 'buffer'

        # send image
        await cast_image(
            image_number=image_number,
            device_number=-1,
            class_name=class_name,
            fps_number=25,
            duration_number=1000,
            retry_number=1,
            buffer_name=buffer_name
        )


async def save_image(class_obj, buffer, image_number, ascii_art=False, interactive=False):
    """
    Save image from Buffer
    used on the buffer images
    """
    folder = app_config['img_folder']
    if folder[-1] == '/':
        pass
    else:
        logger.error("The last character of the folder name is not '/'.")
        return

    # Get the absolute path of the folder relative to the current working directory
    absolute_img_folder = os.path.abspath(folder)
    if os.path.isdir(absolute_img_folder):
        pass
    else:
        logger.error(f"The folder {absolute_img_folder} does not exist.")
        return

    # select buffer
    if buffer == 'frame_buffer':
        buffer = class_obj.frame_buffer
    else:
        buffer = class_obj.cast_frame_buffer

    w, h = buffer[image_number].shape[:2]
    date_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    class_name = class_obj.__module__

    if ascii_art:
        img = buffer[image_number]
        img = Image.fromarray(img)
        img = ImageUtils.image_to_ascii(img)
        filename = folder + class_name + "_" + str(image_number) + "_" + str(w) + "_" + str(
            h) + "_" + date_time + ".txt"
        with open(filename, 'w') as ascii_file:
            ascii_file.write(img)

    else:
        filename = folder + class_name + "_" + str(image_number) + "_" + str(w) + "_" + str(
            h) + "_" + date_time + ".jpg"
        img = cv2.cvtColor(buffer[image_number], cv2.COLOR_RGB2BGR)
        cv2.imwrite(filename, img)

    if interactive:
        ui.notify(f"Image saved to {filename}")

    logger.info(f"Image saved to {filename}")


async def discovery_net_notify():
    """ Call Run zero conf net discovery """

    ui.notification('NET Discovery process on go ... let it finish',
                    close_button=True,
                    type='warning',
                    timeout=6)
    await run_in_threadpool(Netdevice.discover)
    net_view_page.refresh()


async def discovery_media_notify():
    """ Call Run OS Media discovery by av """

    ui.notification('MEDIA Discovery process on go ... let it finish',
                    close_button=True,
                    type='warning',
                    timeout=3)
    await util_device_list_update()
    media_dev_view_page.refresh()


async def init_cast(class_obj, clog_ui=None):
    """
    Run the cast and refresh the cast view
    :param class_obj:
    :param clog_ui:
    :return:
    """
    class_obj.cast(shared_buffer=t_data_buffer)
    await cast_manage()
    logger.info(f' Run Cast for {str(class_obj)}')
    ui.notify(f'Cast initiated for :{str(class_obj)} ')


async def cast_stop(class_obj):
    """ Stop cast """

    class_obj.stopcast = True
    ui.notify(f'Cast(s) stopped and blocked for : {class_obj}', position='center', type='info', close_button=True)
    await cast_manage()
    logger.info(f' Stop Cast for {str(class_obj)}')


async def show_notify(event: ValueChangeEventArguments):
    name = type(event.sender).__name__
    ui.notify(f'{name}: {event.value}')


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
                        ui.button(on_click=lambda: save_image(class_obj, buffer, index, False, True), icon='save') \
                            .props('flat fab color=white') \
                            .tooltip('Save Image')
                        ui.button(on_click=lambda: save_image(class_obj, buffer, index, True, True),
                                  icon='text_format') \
                            .props('flat fab color=white') \
                            .tooltip('Save Image as Ascii ART')

                    ui.label(str(index)).classes('absolute-bottom text-subtitle2 text-center').style('background: red')
                ui.button('Close', on_click=dialog.close, color='red')
            ui.button('', icon='preview', on_click=dialog.open, color='bg-red-800').tooltip('View image')

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'An exception occurred: {error}')


async def multi_preview(class_name):
    """
    Generate matrix image preview for multicast
    :return:
    """
    dialog = ui.dialog().style('width: 200px')
    with dialog:
        grid_col = ''
        for c in range(class_name.cast_x):
            grid_col += '1fr '
        with ui.grid(columns=grid_col).classes('w-full gap-0'):
            for i in range(len(class_name.cast_frame_buffer)):
                with ui.image(Image.fromarray(class_name.cast_frame_buffer[i])).classes('w-60'):
                    ui.label(str(i))
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('FULL', icon='preview', on_click=dialog.open).tooltip('View ALL images')


async def cast_devices_view(class_name):
    """
    view cast_devices list
    :return:
    """
    dialog = ui.dialog().style('width: 800px')
    with dialog:
        with ui.card():
            with ui.grid(columns=3):
                for i in range(len(class_name.cast_devices)):
                    with ui.card():
                        ui.label('No: ' + str(class_name.cast_devices[i][0]))
                        if Utils.validate_ip_address(str(class_name.cast_devices[i][1])):
                            text_decoration = "color: green; text-decoration: underline"
                        else:
                            text_decoration = "color: red; text-decoration: red wavy underline"

                        ui.link('IP  :  ' + str(class_name.cast_devices[i][1]),
                                'http://' + str(class_name.cast_devices[i][1]),
                                new_tab=True).style(text_decoration)
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('DEVICE', icon='preview', on_click=dialog.open).tooltip('View Cast devices')


async def player_pick_file() -> None:
    """ Select file to read for video CastAPI.player"""

    result = await LocalFilePicker('./', multiple=False)
    ui.notify(f'Selected :  {result}')

    if result is not None:
        if sys.platform.lower() == 'win32':
            result = str(result[0]).replace('\\', '/')

        CastAPI.player.set_source(result)
        CastAPI.player.update()


async def check_yt(url):
    """Check Download youtube video"""
    video_url = url
    CastAPI.progress_bar.value = 0
    CastAPI.progress_bar.update()

    async def get_size():
        while True:
            if Utils.yt_file_size_remain_bytes == 0:
                break

            else:
                CastAPI.progress_bar.value = 1 - (Utils.yt_file_size_remain_bytes / Utils.yt_file_size_bytes)
                CastAPI.progress_bar.update()
                await asyncio.sleep(.1)

    asyncio.create_task(get_size())

    if 'https://youtu' in url:
        yt = await Utils.youtube(url, interactive=True)
        if yt != '':
            video_url = yt

    ui.notify(f'Video set to : {video_url}')
    logger.info(f'Video set to : {video_url}')
    CastAPI.progress_bar.value = 1
    CastAPI.progress_bar.update()
    CastAPI.player.set_source(video_url)
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
    ui.colors(primary=color_config['primary'],
              secondary=color_config['secondary'],
              accent=color_config['accent'],
              dark=color_config['dark'],
              positive=color_config['positive'],
              negative=color_config['negative'],
              info=color_config['info'],
              warning=color_config['warning']
              )

    ui.query('body').style(f'background-image: url({custom_config["bg-image"]}); '
                           'background-size: cover;'
                           'background-repeat: no-repeat;'
                           'background-position: center;')


"""
RUN
"""

app.openapi = custom_openapi
app.add_static_files('/assets', 'assets')
app.add_media_files('/media', 'media')
app.add_static_files('/log', 'log')
app.add_static_files('/config', 'config')
app.add_static_files('/tmp', 'tmp')
app.add_static_files('/xtra', 'xtra')
app.on_startup(init_actions)

ui.run(title='WLEDVideoSync',
       favicon='favicon.ico',
       host=server_ip,
       port=server_port,
       show=True,
       reconnect_timeout=int(server_config['reconnect_timeout']),
       reload=False)

"""
END
"""
if sys.platform != 'win32':
    logger.info('Remove tmp files')
    for tmp_filename in PathLib("./tmp/").glob("*_file.*"):
        tmp_filename.unlink()

    # remove yt files
    if str2bool(app_config['keep_yt']) is not True:
        for media_filename in PathLib("./media/").glob("yt-tmp-*.*"):
            media_filename.unlink()
