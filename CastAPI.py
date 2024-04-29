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

API: FastAPI, for integration with third party application (e.g. Chataigne)

Web GUI based on NiceGUI

"""
import logging
import logging.config
import traceback

import asyncio
import threading

from ddp_queue import DDPDevice

import time
import sys
import socket
import json
import os

import cv2

import queue

import cfg_load as cfg

import desktop
import media
from utils import CASTUtils as Utils, LogElementHandler
from utils import HTTPDiscovery as Net
from utils import ImageUtils

import ast

from typing import Union
from datetime import datetime
from str2bool import str2bool

from PIL import Image

from fastapi.openapi.utils import get_openapi
from fastapi import HTTPException, Path, WebSocket
from starlette.concurrency import run_in_threadpool

from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments

Desktop = desktop.CASTDesktop()
Media = media.CASTMedia()
Netdevice = Net()

class_to_test = ['Desktop', 'Media', 'Netdevice']
action_to_test = ['stop', 'buffer', 'info', 'close_preview']

app.debug = False

# read config
logging.config.fileConfig('config/logging.ini')
# create logger
logger = logging.getLogger('WLEDLogger.api')

# load config file
cast_config = cfg.load('config/WLEDVideoSync.ini')

# config keys
server_config = cast_config.get('server')
app_config = cast_config.get('app')
color_config = cast_config.get('colors')

# Validate network config
server_ip = server_config['server_ip']
if not Utils.validate_ip_address(server_ip):
    print(f'Bad server IP: {server_ip}')
    sys.exit(1)
server_port = int(server_config['server_port'])
if server_port not in range(1, 65536):
    print(f'Bad server Port: {server_port}')
    sys.exit(2)

# to share data between threads and main
t_data_buffer = queue.Queue()  # create a thread safe queue


class CastAPI:
    dark_mode = False


"""
FastAPI
"""


@app.get("/api")
async def read_api_root():
    """
        Status: see if WLEDVideoSync is running
    """
    return {"Status": "WLEDVideoSync is Running ..."}


@app.get("/api/{class_obj}/params")
async def all_params(class_obj: str = Path(description=f'Class name, should be in: {class_to_test}')):
    """
        Retrieve all 'params' from a class
    """
    if class_obj not in class_to_test:
        raise HTTPException(status_code=400, detail=f"Class name: {class_obj} not in {class_to_test}")
    return {"all_params": vars(globals()[class_obj])}


@app.get("/api/{class_obj}/run_cast")
async def run_cast(class_obj: str):
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


@app.get("/api/util/active_win")
async def util_active_win():
    """
       Show title from actual active window
    """
    return {"window_title": Utils.active_window()}


@app.get("/api/util/win_titles")
async def util_win_titles():
    """
        Retrieve all titles from windows
    """
    return {"windows_titles": Utils.windows_titles()}


@app.get("/api/util/device_list")
async def util_device_list():
    """
        Show available devices
    """
    return {"device_list": Utils.dev_list}


@app.get("/api/util/device_list_update")
async def util_device_list_update():
    """
        Update available devices list
    """
    status = "Error"
    if Utils.dev_list_update():
        status = "Ok"
    return {"device_list": status}


@app.get("/api/util/device_net_scan")
async def util_device_net_scan():
    """
        Scan network devices with zeroconf
    """
    # run in non-blocking mode
    await run_in_threadpool(Netdevice.discover)
    return {"net_device_list": 'done'}


@app.get("/api/util/blackout")
async def util_blackout():
    """
        Put ALL ddp devices Off and stop all Casts
    """
    logger.warning('** BLACKOUT **')
    Desktop.t_exit_event.set()
    Media.t_exit_event.set()
    Desktop.stopcast = True
    Media.stopcast = True

    if Desktop.wled:
        await Utils.put_wled_live(Desktop.host, on=False, live=False, timeout=1)
        if Desktop.multicast:
            for item in Desktop.cast_devices:
                await Utils.put_wled_live(item[1], on=False, live=False, timeout=1)
    if Media.wled:
        await Utils.put_wled_live(Media.host, on=False, live=False, timeout=1)
        if Media.multicast:
            for item in Media.cast_devices:
                await Utils.put_wled_live(item[1], on=False, live=False, timeout=1)

    return {"blackout": 'done'}


@app.get("/api/util/casts_info")
def util_casts_info():
    """
        Get info from all Cast Threads
    """
    logger.info('Request Cast(s) info')

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
    logger.info(f'Need to receive info from : {child_list}')

    # iterate through all Cast Names
    for item in child_list:
        # wait and get info dict from a thread
        try:
            data = t_data_buffer.get(timeout=3)
            child_info_data.update(data)
            t_data_buffer.task_done()
        except queue.Empty:
            logger.warning('Empty queue')
            break

    # sort the dict
    sort_child_info_data = dict(sorted(child_info_data.items()))

    Desktop.t_todo_event.clear()
    Media.t_todo_event.clear()
    logger.info('End request info')

    return {"t_info": sort_child_info_data}


@app.get("/api/{class_name}/list_actions")
async def list_todo_actions(class_name: str):
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


@app.put("/api/{class_name}/cast_actions")
async def action_to_thread(class_name: str,
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
        logger.info(f" To do cleared for {class_obj}'")
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
            logger.info(f"Action '{action}' added successfully to : '{class_obj}'")
            return {"message": f"Action '{action}' added successfully to : '{class_obj}'"}

    else:

        if cast_name is None and action is None:
            if class_name == 'Desktop':
                class_obj.t_desktop_lock.release()
            elif class_name == 'Media':
                class_obj.t_media_lock.release()
            class_obj.t_todo_event.set()
            logger.info(f"Actions in queue will be executed")
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
            logger.info(f"Action '{action}' added successfully to : '{class_obj} and execute is On'")
            return {"message": f"Action '{action}' added successfully to : '{class_obj} and execute is On'"}


@app.put("/api/{class_name}/update_attribute")
async def update_attribute_by_name(class_name: str, param: str, value: Union[int, bool, str]):
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
    if class_name == 'Desktop' and param == 'viinput' and 'desktop ' not in value:
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
                logger.error('WEBSOCKET: received data not compliant to expected format')
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
                await globals()[action](**params)
                # send back if no problem
                await websocket.send_text('{"result":"success"}')

            else:

                logger.error('WEBSOCKET: received data contain unexpected action')
                await websocket.send_text('{"result":"error"}')
                raise Exception

    except Exception as error:
        logger.error(traceback.format_exc())
        logger.error('WEBSOCKET An exception occurred: {}'.format(error))
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

    ddp = DDPDevice(ip)

    start_time = time.time() * 1000  # Get the start time in ms
    end_time = start_time + duration_number  # Calculate the end time

    if class_obj.protocol == "ddp":
        while time.time() * 1000 < end_time:  # Loop until current time exceeds end time in ms
            # Send x frames here
            ddp.flush(images_buffer[image_number], retry_number)
            if fps_number != 0:
                time.sleep(1 / fps_number)  # Sleep in s for the time required to send one frame


"""
NiceGUI
"""


@ui.page('/')
def main_page():
    """
    Root page definition
    """
    dark = ui.dark_mode(CastAPI.dark_mode).bind_value_to(CastAPI, 'dark_mode')

    apply_colors()

    """
    timer created on main page run to refresh datas
    """
    ui.timer(int(app_config['timer']), callback=root_timer_action)

    """
    Header with button menu
    """
    with ui.header(bordered=True, elevated=True).classes('items-center shadow-lg'):
        ui.link('MAIN', target='/').classes('text-white text-lg font-medium')
        ui.icon('home')
        # Create buttons
        ui.button('Manage', on_click=lambda: ui.navigate.to('/CastManage'), icon='video_settings')
        ui.button('Desktop Params', on_click=lambda: ui.navigate.to('/Desktop'), icon='computer')
        ui.button('Media Params', on_click=lambda: ui.navigate.to('/Media'), icon='image')
        ui.button('API', on_click=lambda: ui.navigate.to('/docs', new_tab=True), icon='api')

    """
    App info
    """

    with ui.row().classes('w-full no-wrap'):
        ui.label('DESKTOP: Cast Screen / Window content').classes('bg-slate-400 w-1/3')
        with ui.card().classes('bg-slate-400 w-1/3'):
            ui.image("/assets/favicon.ico").classes('self-center').tailwind.border_width('8').width('8')
        ui.label('MEDIA: Cast Image / Video / Capture Device (e.g. USB Camera ...)').classes('bg-slate-400 w-1/3')

    ui.separator().classes('mt-6')

    ui.image("/assets/intro.gif").classes('self-center').tailwind.border_width('8').width('1/6')

    """
    Row for Cast info / Run / Close : refreshable
    """
    with (ui.row().classes('self-center')):
        with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]'):
            ui.label('Filters/Effects')
            with ui.column():
                ui.checkbox('Flip') \
                    .bind_value_to(Desktop, 'flip')
                ui.number('type', min=0, max=1) \
                    .bind_value_to(Desktop, 'flip_vh', lambda value: int(value or 0))

        with ui.card():
            # refreshable
            cast_manage()
            # no refreshable
            ui.icon('info') \
                .tooltip('Show details') \
                .on('click', lambda: show_thread_info()) \
                .classes('self-center') \
                .style('cursor: pointer')

        with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]'):
            ui.label('Filters/Effects')
            with ui.column():
                ui.checkbox('Flip') \
                    .bind_value_to(Media, 'flip')
                ui.number('type', min=0, max=1) \
                    .bind_value_to(Media, 'flip_vh', lambda value: int(value or 0))

    ui.separator().classes('mt-6')

    """
    Log display
    """
    """
    log = ui.log(max_lines=50).classes('w-full h-20')
    logger.addHandler(LogElementHandler(log))
    ui.button('Clear Log', on_click=lambda: log.clear()).tooltip('Erase the log file')
    """

    """
    Footer : usefully links help
    """
    with (ui.footer(value=False).classes('items-center bg-red-900') as footer):
        ui.switch("White/Dark Mode", on_change=dark.toggle).classes('bg-red-900').tooltip('Change Layout Mode')

        net_view_page()  # refreshable

        ui.button('Run discovery', on_click=discovery_net_notify, color='bg-red-800')
        with ui.row().classes('absolute inset-y-0 right-0.5 bg-red-900'):
            ui.link('® Zak-45 ' + str(datetime.now().strftime('%Y')), 'https://github.com/zak-45', new_tab=True) \
                .classes('text-white')
            ui.link('On-Line Help', 'https://github.com/zak-45/WLEDVideoSync', new_tab=True) \
                .tooltip('Go to documentation').classes('text-white')

    with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
        ui.button(on_click=footer.toggle).props('fab icon=contact_support')


@ui.page('/CastManage')
def main_page_cast_manage():
    """ Cast manage with full details page """

    ui.dark_mode(CastAPI.dark_mode)

    apply_colors()

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
    tabs_info_page()

    """
    Footer
    """
    with ui.footer():
        ui.button('Refresh Page', on_click=lambda: ui.navigate.to('/CastManage'))

        net_view_page()

        media_dev_view_page()


@ui.page('/Desktop')
def main_page_desktop():
    """
    Desktop param page
    """
    ui.dark_mode(CastAPI.dark_mode)

    apply_colors()

    with ui.header():
        ui.label('Desktop').classes('text-lg font-medium')
        ui.icon('computer')
        ui.button('MAIN', on_click=lambda: ui.navigate.to('/'), icon='home')

    columns_a = [
        {'name': 'rate', 'label': 'FPS', 'field': 'rate', 'align': 'left'},
        {'name': 'scale_width', 'label': 'H', 'field': 'scale_width'},
        {'name': 'scale_height', 'label': 'V', 'field': 'scale_height'}
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

    exp_param = ui.expansion('Parameters', icon='settings', value=True)
    with exp_param.classes('w-full'):

        cast_icon(Desktop)

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

    exp_edit_param = ui.expansion('Edit', icon='edit', on_value_change=lambda: exp_param.close())
    with exp_edit_param.classes('w-full'):
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

            with ui.card():
                new_vooutput = ui.input('Output', value=str(Desktop.vooutput))
                new_vooutput.bind_value_to(Desktop, 'vooutput')
                new_voformat = ui.input('Codec', value=Desktop.voformat)
                new_voformat.bind_value_to(Desktop, 'voformat')

            with ui.card():
                new_put_to_buffer = ui.input('Capture Frame', value=str(Desktop.put_to_buffer))
                new_put_to_buffer.bind_value_to(Desktop, 'put_to_buffer', lambda value: str2bool(value))
                new_frame_max = ui.number('Number to Capture', value=Desktop.frame_max, min=1, max=30, precision=0)
                new_frame_max.tooltip('Max number of frame to capture')
                new_frame_max.bind_value_to(Desktop, 'frame_max', lambda value: int(value or 0))

    ui.separator().classes('mt-6')

    with ui.expansion('BUFFER', icon='grid_view', on_value_change=lambda: exp_edit_param.close()) \
            .classes('w-full'):
        if len(Desktop.frame_buffer) > 0:
            with ui.row():
                media_grid = ui.grid(columns=8)
                with media_grid:
                    for i in range(len(Desktop.frame_buffer)):
                        # put fixed size for preview
                        img = Utils.resize_image(Desktop.frame_buffer[i], 640, 480)
                        img = Image.fromarray(img)
                        light_box_image(i, img, '', '', Desktop)
                with ui.carousel(animated=True, arrows=True, navigation=True).props('height=480px'):
                    generate_carousel(Desktop)

        else:

            ui.label('No image to show...')

    with ui.footer():

        net_view_page()

        with ui.dialog() as dialog, ui.card():
            win_title = Utils.windows_titles()
            editor = ui.json_editor({'content': {'json': win_title}})
            editor.run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog.close, color='red')
        ui.button('Win TITLES', on_click=dialog.open, color='bg-red-800').tooltip('View windows titles')


@ui.page('/Media')
def main_page_media():
    """
    Media param page
    """
    ui.dark_mode(CastAPI.dark_mode)

    apply_colors()

    with ui.header():
        ui.link('MEDIA', target='/Media').classes('text-white text-lg font-medium')
        ui.icon('image')
        ui.button('Main', on_click=lambda: ui.navigate.to('/'), icon='home')

    columns_a = [
        {'name': 'rate', 'label': 'FPS', 'field': 'rate', 'align': 'left'},
        {'name': 'scale_width', 'label': 'H', 'field': 'scale_width'},
        {'name': 'scale_height', 'label': 'V', 'field': 'scale_height'}
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
    with media_exp_param.classes('w-full'):

        cast_icon(Media)

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

    media_exp_edit_param = ui.expansion('Edit', icon='edit', on_value_change=lambda: media_exp_param.close())
    with media_exp_edit_param.classes('w-full'):
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

    ui.separator().classes('mt-6')

    with ui.expansion('BUFFER', icon='grid_view', on_value_change=lambda: media_exp_edit_param.close()) \
            .classes('w-full'):
        if len(Media.frame_buffer) > 0:
            with ui.row():
                media_grid = ui.grid(columns=8)
                with media_grid:
                    for i in range(len(Media.frame_buffer)):
                        # put fixed size for preview
                        img = Utils.resize_image(Media.frame_buffer[i], 640, 480)
                        img = Image.fromarray(img)
                        light_box_image(i, img, '', '', Media)
                with ui.carousel(animated=True, arrows=True, navigation=True).props('height=480px'):
                    generate_carousel(Media)

        else:

            ui.label('No image to show...')

    with ui.expansion('MULTICAST', icon='grid_view', on_value_change=lambda: media_exp_edit_param.close()) \
            .classes('w-full'):
        # columns number  = cast_x, number of cards = cast_x * cast_y
        if Media.multicast:
            with ui.row():
                multi_preview()
                cast_devices_view()
            if len(Media.cast_frame_buffer) > 0:
                with ui.grid(columns=Media.cast_x):
                    try:
                        for i in range(Media.cast_x * Media.cast_y):
                            light_box_image(i, Image.fromarray(Media.cast_frame_buffer[i]), i, '', Media)
                    except Exception as error:
                        logger.error(traceback.format_exc())
                        logger.error('An exception occurred: {}'.format(error))
            else:
                ui.label('No frame captured yet...')
        else:
            with ui.card():
                ui.label('Multicast not set').style('text-align:center; font-size: 150%; font-weight: 300')

    ui.separator().classes('mt-6')

    with ui.footer():

        net_view_page()

        media_dev_view_page()
        ui.button('Run discovery', on_click=discovery_media_notify, color='bg-red-800')


@ui.page('/WLEDVideoSync')
def splash_page():
    """
    Page displayed on the webview window
    :return:
    """
    ui.dark_mode(True)
    ui.image('assets/intro.gif').classes('self-center').style('width: 50%')
    ui.button('MAIN INTERFACE', on_click=lambda: ui.navigate.to(f'http://{server_ip}:{server_port}/')) \
        .classes('self-center')
    ui.button('API', on_click=lambda: ui.navigate.to(f'http://{server_ip}:{server_port}/docs')) \
        .classes('self-center')


@ui.page('/ws/docs')
def ws_page():
    """
    websocket docs page
    :return:
    """
    ui.label('WEBSOCKETS Doc').classes('self-center')
    doc_txt = ui.textarea('WE endpoints').style('width: 50%')
    doc_txt.value = ('Use /cast_image:x:z:f:d:r:c:i to send image number x (Media.buffer[x])'
                     ' to cast device z (Media.cast_devices[z])'
                     'image_number = int'
                     'device_number = int if -1 take host'
                     'class_name = str (Desktop or Media)'
                     'fps_number = int max 60'
                     'duration_number = int'
                     'retry_number = int if < 0 set to 0'
                     'buffer_name = BUFFER or  MULTICAST'
                     )


@ui.page('/info')
def info_page():
    """ simple cast info page from systray """
    ui.timer(int(app_config['timer']), callback=info_timer_action)
    cast_manage()


@ui.page('/DetailsInfo')
def manage_info_page():
    """ Manage cast page from systray """
    tabs_info_page()


@ui.refreshable
def cast_manage():
    """
    refreshable cast parameters  on the root page '/'
    :return:
    """
    with ui.card().classes('self-center'):
        with ui.row():
            with ui.column(wrap=True):
                if Desktop.count > 0:
                    my_col = 'red'
                elif Desktop.stopcast:
                    my_col = 'yellow'
                else:
                    my_col = 'green'
                ui.icon('cast', size='xl', color=my_col)
                if not Desktop.stopcast:
                    ui.button(icon='touch_app', on_click=lambda: init_cast(Desktop)) \
                        .classes('shadow-lg') \
                        .tooltip('Initiate Desktop Cast')

            ui.icon('stop_screen_share', size='xs', color='red') \
                .style('cursor: pointer') \
                .on('click', lambda: cast_stop(Desktop)).tooltip('Stop Cast')

            with ui.card().classes('bg-red-900'):
                ui.label(' Running Cast(s) ').classes('self-center').style("color: yellow; background: purple")
                with ui.row():
                    ui.label('Desktop: ' + str(Desktop.count)).style('color: yellow')
                    ui.label('Media: ' + str(Media.count)).style('color: yellow')

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
                ui.icon('cast', size='xl', color=my_col)
                if not Media.stopcast:
                    ui.button(icon='touch_app', on_click=lambda: init_cast(Media)) \
                        .classes('shadow-lg') \
                        .tooltip('Initiate Media Cast')


@ui.refreshable
def cast_icon(class_obj):
    """
    refreshable Icon color on '/Desktop' and '/Media' pages
    :param class_obj:
    :return:
    """
    cast_col = 'green' if class_obj.stopcast is False else 'yellow'
    ui.icon('cast_connected', size='sm', color=cast_col) \
        .style('cursor: pointer') \
        .on('click', lambda: cast_icon_color(class_obj)) \
        .tooltip('Click to authorize')


@ui.refreshable
def net_view_page():
    """
    Display network devices into the Json Editor
    :return:
    """
    with ui.dialog() as dialog, ui.card():
        editor = ui.json_editor({'content': {'json': Netdevice.http_devices}})
        editor.run_editor_method('updateProps', {'readOnly': True})
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('Net devices', on_click=dialog.open, color='bg-red-800').tooltip('View network devices')


@ui.refreshable
def media_dev_view_page():
    """
    Display network devices into the Json Editor
    :return:
    """
    with ui.dialog() as dialog, ui.card():
        editor = ui.json_editor({'content': {'json': Utils.dev_list}})
        editor.run_editor_method('updateProps', {'readOnly': True})
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('Media devices', on_click=dialog.open, color='bg-red-800').tooltip('View Media devices')


"""
helpers
"""


def tabs_info_page():
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

    with ui.tabs().classes('w-full') as tabs:
        p_desktop = ui.tab('Desktop', icon='computer').classes('bg-slate-400')
        p_media = ui.tab('Media', icon='image').classes('bg-slate-400')
    with ui.tab_panels(tabs, value=p_desktop).classes('w-full'):
        with ui.tab_panel(p_desktop):
            if not desktop_threads:
                ui.label('No CAST').style('text-align:center; font-size: 150%; font-weight: 300')
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
                                              on_click=lambda item=item, item_exp=item_exp: action_from_tabs(
                                                  class_name='Desktop',
                                                  cast_name=item,
                                                  action='stop',
                                                  clear=False,
                                                  execute=True,
                                                  exp_item=item_exp)
                                              ).classes('shadow-lg').tooltip('Cancel Cast')
                                    ui.button(icon='add_photo_alternate',
                                              on_click=lambda item=item: action_from_tabs(class_name='Desktop',
                                                                                          cast_name=item,
                                                                                          action='buffer',
                                                                                          clear=False,
                                                                                          execute=True)
                                              ).classes('shadow-lg').tooltip('Capture picture')
                                    if info_data[item]["data"]["preview"]:
                                        ui.button(icon='cancel_presentation',
                                                  on_click=lambda item=item: action_from_tabs(class_name='Desktop',
                                                                                              cast_name=item,
                                                                                              action='close_preview',
                                                                                              clear=False,
                                                                                              execute=True)
                                                  ).classes('shadow-lg').tooltip('Stop Preview')

                                editor = ui.json_editor({'content': {'json': info_data[item]["data"]}})
                                editor.run_editor_method('updateProps', {'readOnly': True})

        with ui.tab_panel(p_media):
            if not media_threads:
                ui.label('No CAST').style('text-align:center; font-size: 150%; font-weight: 300')
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
                                              on_click=lambda item=item, item_exp=item_exp: action_from_tabs(
                                                  class_name='Media',
                                                  cast_name=item,
                                                  action='stop',
                                                  clear=False,
                                                  execute=True,
                                                  exp_item=item_exp)
                                              ).classes('shadow-lg').tooltip('Cancel Cast')
                                    ui.button(icon='add_photo_alternate',
                                              on_click=lambda item=item: action_from_tabs(class_name='Media',
                                                                                          cast_name=item,
                                                                                          action='buffer',
                                                                                          clear=False,
                                                                                          execute=True)
                                              ).classes('shadow-lg').tooltip('Capture picture')
                                    if info_data[item]["data"]["preview"]:
                                        ui.button(icon='cancel_presentation',
                                                  on_click=lambda item=item: action_from_tabs(class_name='Media',
                                                                                              cast_name=item,
                                                                                              action='close_preview',
                                                                                              clear=False,
                                                                                              execute=True)
                                                  ).classes('shadow-lg').tooltip('Stop Preview')

                                editor = ui.json_editor({'content': {'json': info_data[item]["data"]}})
                                editor.run_editor_method('updateProps', {'readOnly': True})


async def action_from_tabs(class_name, cast_name, action, clear, execute, exp_item=None):
    await action_to_thread(class_name, cast_name, action, clear, execute)
    if action == 'stop':
        exp_item.close()
        ui.notification(f'Stopping {cast_name}...', type='warning', position='center', timeout=1)
        exp_item.delete()
    elif action == 'buffer':
        ui.notification(f'Saving image to buffer for  {cast_name}...', type='positive', timeout=1)
    elif action == 'close_preview':
        ui.notification(f'Preview window terminated for  {cast_name}...', type='info', timeout=1)


def show_thread_info():
    with ui.dialog() as dialog, ui.card():
        cast_info = util_casts_info()
        editor = ui.json_editor({'content': {'json': cast_info}})
        editor.run_editor_method('updateProps', {'readOnly': True})
        ui.button('Close', on_click=dialog.close, color='red')
        dialog.open()


async def cast_icon_color(class_obj):
    """ icon color """
    class_obj.stopcast = False
    cast_icon.refresh()


async def root_timer_action():
    """
    timer occur only when root page is active '/'
    :return:
    """
    #  print('timer action')
    cast_manage.refresh()


async def info_timer_action():
    """
    timer occur only when info page is active '/info'
    :return:
    """
    #  print('timer action')
    cast_manage.refresh()


def generate_carousel(class_obj):
    """ Images carousel for Desktop and Media """

    for i in range(len(class_obj.frame_buffer)):
        with ui.carousel_slide().classes('-p0'):
            carousel_image = Image.fromarray(class_obj.frame_buffer[i])
            h, w = class_obj.frame_buffer[i].shape[:2]
            img = ui.interactive_image(carousel_image.resize(size=(640, 480))).classes('w-[640]')
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
        ui.notify('No WLED device', type='negative')
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


async def save_image(class_obj, image_number, ascii_art=False):
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

    w, h = class_obj.frame_buffer[image_number].shape[:2]
    date_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    class_name = class_obj.__module__

    if ascii_art:
        img = class_obj.frame_buffer[image_number]
        img = Image.fromarray(img)
        img = ImageUtils.image_to_ascii(img)
        filename = folder + class_name + "_" + str(image_number) + "_" + str(w) + "_" + str(
            h) + "_" + date_time + ".txt"
        with open(filename, 'w') as ascii_file:
            ascii_file.write(img)

    else:
        filename = folder + class_name + "_" + str(image_number) + "_" + str(w) + "_" + str(
            h) + "_" + date_time + ".jpg"
        img = cv2.cvtColor(class_obj.frame_buffer[image_number], cv2.COLOR_RGB2BGR)
        cv2.imwrite(filename, img)

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


async def init_cast(class_obj):
    """
    Run the cast and refresh the cast view
    :param class_obj:
    :return:
    """
    class_obj.cast(shared_buffer=t_data_buffer)
    cast_manage.refresh()
    logger.info(datetime.now().strftime('%X.%f')[:-5] + ' Run Cast for ' + str(class_obj))
    # just try to avoid mad man click !!
    time.sleep(2)


async def cast_stop(class_obj):
    """ Stop cast """

    class_obj.stopcast = True
    cast_manage.refresh()
    logger.info(datetime.now().strftime('%X.%f')[:-5] + ' Stop Cast for ' + str(class_obj))


async def show_notify(event: ValueChangeEventArguments):
    name = type(event.sender).__name__
    ui.notify(f'{name}: {event.value}')


def table_page(columns_x, rows_y):
    list_columns, list_rows = generate_table(columns_x, rows_y)
    ui.table(columns=list_columns, rows=list_rows).props('separator="cell" hide-header')


def generate_table(columns_x, rows_y):
    # Generate columns
    list_columns = [{'name': str(i), 'label': f'Label {i}', 'field': str(i)} for i in range(columns_x)]

    # Generate rows
    list_rows = []
    for i in range(rows_y):
        row = {'name': str(i)}
        for j in range(columns_x):
            row[str(j)] = str(i * columns_x + j)
        list_rows.append(row)

    return list_columns, list_rows


def light_box_image(index, image, txt1, txt2, class_obj):
    """
    Provide basic 'lightbox' effect for image
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

            with ui.dialog() as dialog:
                dialog.style('width: 800px')
                ui.label(str(index)) \
                    .tailwind.font_weight('extrabold').text_color('red-600').background_color('orange-200')
                with ui.interactive_image(image):
                    with ui.row().classes('absolute top-0 left-0 m-2'):
                        ui.button(on_click=lambda: cast_to_wled(class_obj, index), icon='cast') \
                            .props('flat fab color=white') \
                            .tooltip('Cast to WLED')
                        ui.button(on_click=lambda: save_image(class_obj, index), icon='save') \
                            .props('flat fab color=white') \
                            .tooltip('Save Image')
                        ui.button(on_click=lambda: save_image(class_obj, index, ascii_art=True), icon='text_format') \
                            .props('flat fab color=white') \
                            .tooltip('Save Image as Ascii ART')

                    ui.label(str(index)).classes('absolute-bottom text-subtitle2 text-center').style('background: red')
                ui.button('Close', on_click=dialog.close, color='red')
            ui.button('', icon='preview', on_click=dialog.open, color='bg-red-800').tooltip('View image')

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error('An exception occurred: {}'.format(error))


def multi_preview():
    """
    Generate matrix image preview for multicast
    :return:
    """
    with ui.dialog() as dialog:
        dialog.style('width: 200px')
        grid_col = ''
        for c in range(Media.cast_x):
            grid_col += '1fr '
        with ui.grid(columns=grid_col).classes('w-full gap-0'):
            for i in range(len(Media.cast_frame_buffer)):
                with ui.image(Image.fromarray(Media.cast_frame_buffer[i])).classes('w-60'):
                    ui.label(str(i))
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('FULL', icon='preview', on_click=dialog.open).tooltip('View ALL images')


def cast_devices_view():
    """
    view cast_devices list
    :return:
    """
    with ui.dialog() as dialog:
        dialog.style('width: 800px')
        with ui.card():
            with ui.grid(columns=3):
                for i in range(len(Media.cast_devices)):
                    with ui.card():
                        ui.label('No: ' + str(Media.cast_devices[i][0]))
                        if Utils.validate_ip_address(str(Media.cast_devices[i][1])):
                            text_decoration = "color: green; text-decoration: underline"
                        else:
                            text_decoration = "color: red; text-decoration: red wavy underline"

                        ui.link('IP  :  ' + str(Media.cast_devices[i][1]),
                                'http://' + str(Media.cast_devices[i][1]),
                                new_tab=True).style(text_decoration)
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('DEVICE', icon='preview', on_click=dialog.open).tooltip('View Cast devices')


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
            "summary": "WebSocket - only for reference",
            "description": websocket_info,
            "responses": {200: {}},
            "tags": "W"
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def apply_colors():
    """
    Layout Colors come from config file
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


"""
RUN
"""
app.openapi = custom_openapi
app.add_static_files('/assets', 'assets')
app.add_static_files('/media', 'media')
app.add_static_files('/log', 'log')

ui.run(title='WLEDVideoSync',
       favicon='favicon.ico',
       show=False,
       host=server_ip,
       port=server_port,
       reconnect_timeout=int(server_config['reconnect_timeout']),
       endpoint_documentation='none',
       reload=False)
