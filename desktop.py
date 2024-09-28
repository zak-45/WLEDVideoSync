# a: zak-45
# d: 13/03/2024
# v: 1.0.0
#
# CASTDesktop class
#
#           Cast your screen to ddp device (e.g.WLED)
#                               or others
#
# logger.info(av.codec.codecs_available)
# pyav --codecs
#
# windows : ffmpeg -f gdigrab -framerate 30 -video_size 640x480 -show_region 1 -i desktop output.mkv
# linux   : ffmpeg -video_size 1024x768 -framerate 25 -f x11grab -i :0.0+100,200 output.mp4
# darwin  : ffmpeg -f avfoundation -i "<screen device index>:<audio device index>" output.mkv
#
# By using PyAV, ffmpeg do not need to be installed on the OS.
# PyAV is a Pythonic binding for ffmpeg.
# This utility aim to be cross-platform.
# You can cast your entire desktop screen or only window content or desktop area.
# Data will be sent through 'ddp' protocol or stream via udp:// rtp:// etc ...
# ddp data are sent by using queue feature to avoid any network problem which cause latency
# 27/05/2024: cv2.imshow with import av  freeze on not win OS
# to fix it, cv2.imshow can run from its own process with cost of additional overhead: set preview_proc = True
#

import sys
import os

import imageio.v3 as iio

import cv2
import logging
import logging.config
import concurrent_log_handler

from multiprocessing.shared_memory import ShareableList
import traceback

import time

import cfg_load as cfg
from str2bool import str2bool

import threading

from asyncio import run
import concurrent.futures

from ddp_queue import DDPDevice
from utils import CASTUtils as Utils
from cv2utils import CV2Utils, ImageUtils

import av

from multicast import IPSwapper


Process, Queue = Utils.mp_setup()

"""
When this env var exist, this mean run from the one-file executable.
Load of the config is not possible, folder config should not exist.
This avoid FileNotFoundError.
This env not exist when run the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    # read config
    # create logger
    logger = Utils.setup_logging('config/logging.ini', 'WLEDLogger.desktop')

    """
    Retrieve  config keys
    """

    cfg_text = False
    if os.path.isfile('config/WLEDVideoSync.ini'):
        # load config file
        cast_config = cfg.load('config/WLEDVideoSync.ini')

        # config keys
        app_config = cast_config.get('app')
        desktop_config = cast_config.get('desktop')
        config_text = app_config['text']
        if str2bool(config_text) is True:
            cfg_text = True

"""
Class definition
"""


class CASTDesktop:
    """ Cast Desktop to DDP """

    count = 0  # initialise running casts count to zero
    total_frame = 0  # total number of processed frames

    cast_names = []  # list of running threads
    cast_name_todo = []  # list of cast names that need to execute to do

    t_exit_event = threading.Event()  # thread listen event

    t_todo_event = threading.Event()  # thread listen event for task to do
    t_desktop_lock = threading.Lock()  # define lock for to do

    server_port = Utils.get_server_port()

    total_packet = 0  # net packets number

    def __init__(self):
        self.rate: int = 25
        self.stopcast: bool = True
        self.scale_width: int = 128
        self.scale_height: int = 128
        self.flip_vh: int = 0
        self.flip: bool = False
        self.saturation = 0
        self.brightness = 0
        self.contrast = 0
        self.sharpen = 0
        self.balance_r = 0
        self.balance_g = 0
        self.balance_b = 0
        self.gamma: float = 0.5
        self.auto_bright = False
        self.clip_hist_percent = 25
        self.wled: bool = False
        self.wled_live = False
        self.host: str = '127.0.0.1'
        self.port: int = 4048
        self.protocol: str = 'ddp'  # put 'other' to use vooutput
        self.retry_number: int = 0  # number of time to resend ddp packet
        self.preview_top: bool = False
        self.preview_w: int = 640
        self.preview_h: int = 360
        self.text = cfg_text
        self.custom_text: str = ""
        self.voformat: str = 'mpeg'
        self.vo_codec: str = 'h264'
        self.vooutput: str = 'udp://127.0.0.1:12345?pkt_size=1316'
        self.put_to_buffer: bool = False
        self.frame_buffer: list = []
        self.frame_max: int = 8
        self.multicast: bool = False
        self.cast_x: int = 1
        self.cast_y: int = 1
        self.cast_devices: list = []
        self.cast_frame_buffer = []
        self.monitor_number: int = 0  # monitor to use for area selection
        self.screen_coordinates = []
        self.reset_total = False
        self.preview = True
        self.record = False  # put True to record to file
        self.output_file = "" # Name of the file to save video recording

        if sys.platform.lower() == 'win32':
            self.viinput = 'desktop'  # 'desktop' full screen or 'title=<window title>' or 'area' for portion of screen
            self.viformat: str = 'gdigrab'  # 'gdigrab' for win

        elif sys.platform.lower() == 'linux':
            self.viinput: str = os.getenv('DISPLAY')  # retrieve display from env variable
            self.viformat: str = 'x11grab'

        elif sys.platform.lower() == 'darwin':
            self.viinput = '"<screen device index>:<audio device index>"'
            self.viformat: str = 'avfoundation'

        else:
            self.viinput = ''
            self.viformat = ''

        self.vi_codec: str = 'libx264rgb'
        self.all_windows_titles = Utils.windows_titles()


    def t_desktop_cast(self, shared_buffer=None):
        """
            Cast desktop screen or a window content based on the title
        """

        t_name = threading.current_thread().name
        if CASTDesktop.count == 0 or self.reset_total is True:
            CASTDesktop.total_frame = 0
            CASTDesktop.total_packet = 0

        logger.debug(f'Child thread: {t_name}')

        t_send_frame = threading.Event()  # thread listen event to send frame via ddp, for multicast synchro

        start_time = time.time()
        t_preview = self.preview
        t_multicast = self.multicast
        t_ddp_multi_names =[]
        t_cast_x = self.cast_x
        t_cast_y = self.cast_y
        t_cast_frame_buffer = []

        frame_count = 0

        t_todo_stop = False

        sl_process = None
        sl = None

        """
        Cast devices
        """
        ip_addresses = []

        """
        av 
        """
        output_container = False
        output_stream = None

        """
        MultiCast inner function protected from what happens outside.
        """

        def send_multicast_image(ip, image):
            """
            This sends an image to an IP address using DDP
            :param ip:
            :param image:
            :return:
            """
            # timeout provided to not have thread waiting infinitely
            if t_send_frame.wait(timeout=.5):
                # send ddp data, we select DDPDevice based on the IP
                for dev in t_ddp_multi_names:
                    if ip == dev.name:
                        dev.send_to_queue(image, self.retry_number)
                        CASTDesktop.total_packet += dev.frame_count
                        break
            else:
                logger.warning(f'{t_name} Multicast frame dropped')

        def send_multicast_images_to_ips(images_buffer, to_ip_addresses):
            """
            Create a thread for each image , IP pair and wait for all to finish
            Very simple synchro process
            :param images_buffer:
            :param to_ip_addresses:
            :return:
            """
            with concurrent.futures.ThreadPoolExecutor() as executor:
                if t_multicast and (t_cast_x != 1 or t_cast_y != 1):
                    # Submit a thread for each image and IP pair
                    multicast = [executor.submit(send_multicast_image, ip, image)
                                 for ip, image in zip(to_ip_addresses, images_buffer)]
                else:
                    # Submit a thread for each IP with same image
                    multicast = [executor.submit(send_multicast_image, ip, images_buffer[0])
                                 for ip in to_ip_addresses]

                # once all threads up, need to set event because they wait for
                t_send_frame.set()

                # Wait for all threads to complete
                concurrent.futures.wait(multicast, timeout=1)

            t_send_frame.clear()

        """
        End Multicast
        """

        """
        First, check devices 
        """

        ddp_host = None
        swapper = None
        # check IP
        if self.host != '127.0.0.1':  # 127.0.0.1 should always exist
            if Utils.check_ip_alive(self.host):
                logger.debug(f'{t_name} We work with this IP {self.host} as first device: number 0')
            else:
                logger.error(f'{t_name} Error looks like IP {self.host} do not accept connection to port 80')
                return False

            ddp_host = DDPDevice(self.host)  # init here as queue thread not necessary if 127.0.0.1

        # retrieve matrix setup from wled and set w/h
        if self.wled:
            status = run(Utils.put_wled_live(self.host, on=True, live=True, timeout=1))
            if status:
                self.scale_width, self.scale_height = run(Utils.get_wled_matrix_dimensions(self.host))
            else:
                logger.error(f"{t_name} ERROR to set WLED device {self.host} on 'live' mode")
                return False

        # specifics for Multicast
        if t_multicast:
            # validate cast_devices list
            if not Utils.is_valid_cast_device(str(self.cast_devices)):
                logger.error(f"{t_name} Error Cast device list not compliant to format [(0,'xx.xx.xx.xx')...]")
                return False
            else:
                logger.info(f'{t_name} Virtual Matrix size is : \
                            {str(self.scale_width * t_cast_x)}x{str(self.scale_height * t_cast_y)}')
                # populate ip_addresses list
                for i in range(len(self.cast_devices)):
                    cast_ip = self.cast_devices[i][1]
                    valid_ip = Utils.check_ip_alive(cast_ip, port=80, timeout=2)
                    if valid_ip:
                        if self.wled:
                            status = run(Utils.put_wled_live(cast_ip, on=True, live=True, timeout=1))
                            if not status:
                                logger.error(f"{t_name} ERROR to set WLED device {self.host} on 'live' mode")
                                return False

                        ip_addresses.append(cast_ip)
                        # create ddp device for each IP if not exist
                        ddp_exist = False
                        for device in t_ddp_multi_names:
                            if cast_ip == device._destination:
                                logger.warning(f'{t_name} DDPDevice already exist : {cast_ip} as device number {i}')
                                ddp_exist = True
                                break
                        if ddp_exist is not True:
                            t_ddp_multi_names.append(DDPDevice(cast_ip))
                            logger.debug(f'{t_name} DDP Device Created for IP : {cast_ip} as device number {i}')
                    else:
                        logging.error(f'{t_name} Not able to validate ip : {cast_ip}')

                # initiate IPSwapper
                swapper = IPSwapper(ip_addresses)

        else:

            ip_addresses.append(self.host)

        """
        Second, capture media
        """

        self.frame_buffer = []
        self.cast_frame_buffer = []
        frame_interval = self.rate

        # Open video device (desktop / window)
        input_options = {'c:v': self.vi_codec, 'crf': '0', 'preset': 'ultrafast', 'pix_fmt': 'rgb24',
                         'framerate': str(frame_interval), 'probesize': '100M'}

        if self.viinput == 'area':
            # specific area
            # Calculate crop parameters : ; 19/06/2024 coordinates for 2 monitor need to be reviewed
            width = int(self.screen_coordinates[2] - self.screen_coordinates[0])
            height = int(self.screen_coordinates[3] - self.screen_coordinates[1])
            x = int(self.screen_coordinates[0])
            y = int(self.screen_coordinates[1])

            area_options = {'offset_x': str(x), 'offset_y': str(y),
                            'video_size': f'{width}x{height}',
                            'show_region': '1'}

            input_options |= area_options

        elif self.viinput.lower().startswith('win='):
            # specific window content
            # append title (win) if needed
            if sys.platform.lower() == 'win32':
                self.viinput = 'title=' + self.viinput[4:]
            # retrieve window ID
            elif sys.platform.lower() == 'linux':
                try:
                    # list all id for a title name (should be only one ...)
                    window_ids = []
                    # Iterate through each process
                    for process_name, process_details in self.all_windows_titles.items():
                        # Get the windows dictionary
                        windows = process_details.get("windows", {})
                        # Iterate through each window in the windows dictionary
                        for window_name, window_details in windows.items():
                            # Check if the window name matches the title
                            if window_name == self.viinput[4:]:
                                window_ids.append(window_details["id"])
                    # if no title found, we consider user pass ID by himself
                    if len(window_ids) == 0:
                        win_id = hex(int(self.viinput.lower()[4:]))
                        window_options = {'window_id': str(win_id)}
                    # if found only one, that's cool
                    elif len(window_ids) == 1:
                        win_id = hex(int(window_ids[0]))
                        window_options = {'window_id': str(win_id)}
                    # more than one, do not know what to do
                    else:
                        logger.warning(f'More than one hWnd (ID) returned, you need to put it by yourself: {window_ids}')
                        raise Exception

                    input_options |= window_options

                except Exception as e:
                    logger.error(f'Not able to retrieve Window ID (hWnd) : {e}')
                    return False

        logger.debug(f'Options passed to av: {input_options}')

        """
        viinput can be:
                    desktop or :0 ...  : to stream full screen or a part of the screen
                    title=<window name> : to stream only window content for win
                    window_id : to stream only window content for Linux            
                    or str
        """

        if self.viinput in ['desktop', 'area'] and sys.platform.lower() == 'win32':
            t_viinput = 'desktop'
        elif (self.viinput in ['area'] or self.viinput.lower().startswith('win=')) and sys.platform.lower() == 'linux':
            t_viinput = os.getenv('DISPLAY')
        else:
            t_viinput = self.viinput

        # Open av input container in read mode
        try:

            input_container = av.open(t_viinput, 'r', format=self.viformat, options=input_options)

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'{t_name} An exception occurred: {error}')
            return False

        # Decoding with auto threading...if True Decode using both FRAME and SLICE methods
        if str2bool(desktop_config['multi_thread']) is True:
            input_container.streams.video[0].thread_type = "AUTO"  # Go faster!

        # Define Output via av only if protocol is other
        if 'other' in self.protocol:
            try:

                # Output video in case of UDP or other
                output_options = {}
                output_container = av.open(self.vooutput, 'w', format=self.voformat)
                output_stream = output_container.add_stream(self.vo_codec, rate=self.rate, options=output_options)
                output_stream.width = self.scale_width
                output_stream.height = self.scale_height
                output_stream.pix_fmt = 'yuv420p'

                if str2bool(desktop_config['multi_thread']) is True:
                    output_stream.thread_type = "AUTO"

            except Exception as error:
                logger.error(traceback.format_exc())
                logger.error(f'{t_name} An exception occurred: {error}')
                return False

        """
        Record
        """
        out_file = None

        if self.record:
            out_file = iio.imopen(self.output_file, "w", plugin="pyav")
            out_file.init_video_stream(self.vo_codec, fps=frame_interval)

        """
        End Record
        """

        CASTDesktop.cast_names.append(t_name)
        CASTDesktop.count += 1

        # Main loop
        if input_container:
            # input video stream from container (for decode)
            input_stream = input_container.streams.get(video=0)

            # Main frame loop
            # Stream loop
            try:

                logger.info(f"{t_name} Capture from {t_viinput}")
                logger.debug(f"{t_name} Stopcast value : {self.stopcast}")

                for frame in input_container.decode(input_stream):

                    if self.record and out_file is None:
                        out_file = iio.imopen(self.output_file, "w", plugin="pyav")
                        out_file.init_video_stream(self.vo_codec, fps=frame_interval)

                    frame_count += 1
                    CASTDesktop.total_frame += 1

                    # if global stop or local stop
                    if self.stopcast or t_todo_stop:
                        break

                    """
                    instruct the thread to exit 
                    """
                    if CASTDesktop.t_exit_event.is_set():
                        break

                    if output_container:
                        # we send frame to output only if it exists, here only for test, this bypass ddp etc ...
                        # Convert the frame to YUV format
                        frame_rgb = frame.reformat(width=output_stream.width, height=output_stream.height,
                                                   format='rgb24')

                        # Encode the frame
                        for packet in output_stream.encode(frame_rgb):
                            output_container.mux(packet)
                            """
                            Record
                            """
                            if self.record and out_file is not None:
                                # convert frame to np array
                                frame_np = frame.to_ndarray(format="rgb24")
                                out_file.write_frame(frame_np)

                    else:

                        # resize to default size
                        frame = frame.reformat(self.scale_width, self.scale_height)

                        # convert frame to np array
                        frame = frame.to_ndarray(format="rgb24")

                        # adjust gamma
                        frame = cv2.LUT(frame, ImageUtils.gamma_correct_frame(self.gamma))
                        # auto brightness contrast
                        if self.auto_bright:
                            frame = ImageUtils.automatic_brightness_and_contrast(frame, self.clip_hist_percent)
                        # filters
                        filter_params = [self.saturation,
                                         self.brightness,
                                         self.contrast,
                                         self.sharpen,
                                         self.balance_r,
                                         self.balance_g,
                                         self.balance_b
                                         ]

                        # apply filters if any
                        if any(param != 0 for param in filter_params):
                            # apply filters
                            filters = {"saturation": self.saturation,
                                       "brightness": self.brightness,
                                       "contrast": self.contrast,
                                       "sharpen": self.sharpen,
                                       "balance_r": self.balance_r,
                                       "balance_g": self.balance_g,
                                       "balance_b": self.balance_b}

                            frame = ImageUtils.process_raw_image(frame, filters=filters)

                        # flip vertical/horizontal: 0,1
                        if self.flip:
                            frame = cv2.flip(frame, self.flip_vh)

                        """
                        check if something to do
                        manage concurrent access to the list by using lock feature
                        event clear only when no more item in list
                        """

                        if CASTDesktop.t_todo_event.is_set():
                            logger.debug(f"{t_name} We are inside todo :{CASTDesktop.cast_name_todo}")
                            CASTDesktop.t_desktop_lock.acquire()
                            #  take thread name from cast to do list
                            for item in CASTDesktop.cast_name_todo:
                                name, action, params, added_time = item.split("||")

                                if name not in CASTDesktop.cast_names:
                                    CASTDesktop.cast_name_todo.remove(item)

                                elif name == t_name:
                                    logging.debug(f'To do: {action} for :{t_name}')

                                    # use try to capture any failure
                                    try:
                                        if 'stop' in action:
                                            t_todo_stop = True
                                        elif 'shot' in action:
                                            add_frame = CV2Utils.pixelart_image(frame,
                                                                                self.scale_width,
                                                                                self.scale_height)
                                            add_frame = CV2Utils.resize_image(add_frame,
                                                                              self.scale_width,
                                                                              self.scale_height)
                                            self.frame_buffer.append(add_frame)
                                            if t_multicast:
                                                # resize frame to virtual matrix size
                                                add_frame = CV2Utils.resize_image(frame,
                                                                                  self.scale_width * t_cast_x,
                                                                                  self.scale_height * t_cast_y)

                                                self.cast_frame_buffer = Utils.split_image_to_matrix(add_frame,
                                                                                                     t_cast_x, t_cast_y)
                                        elif 'info' in action:
                                            t_info = {t_name: {"type": "info",
                                                               "data": {"start": start_time,
                                                                        "cast_type": 'Desktop',
                                                                        "tid": threading.current_thread().native_id,
                                                                        "viinput": str(t_viinput),
                                                                        "preview": t_preview,
                                                                        "multicast": t_multicast,
                                                                        "devices": ip_addresses,
                                                                        "fps": frame_interval,
                                                                        "frames": frame_count
                                                                        }
                                                               }
                                                      }
                                            # this wait until queue access is free
                                            shared_buffer.put(t_info)
                                            logger.debug(f"{t_name} we have put on the queue")

                                        elif "close_preview" in action:
                                            CV2Utils.cv2_win_close(CASTDesktop.server_port, 'Desktop', t_name, t_viinput)
                                            t_preview = False

                                        elif "open_preview" in action:
                                            t_preview = True

                                        elif "reset" in action:
                                            CASTDesktop.total_frame = 0
                                            CASTDesktop.total_packet = 0
                                            self.reset_total = False

                                        elif "host" in action:
                                            ip_addresses[0] = params
                                            if ddp_host is not None:
                                                ddp_host._destination = params
                                            else:
                                                ddp_host=DDPDevice(params)

                                        elif "multicast" in action:
                                            if t_multicast:
                                                if params == 'stop':
                                                    swapper.stop()
                                                else:
                                                    action_arg, delay_arg = params.split(',')
                                                    delay_arg = int(delay_arg)
                                                    if swapper.running:
                                                        logger.warning(f'{t_name} Already a running effect')
                                                    else:
                                                        if action_arg == 'circular':
                                                            swapper.start_circular_swap(delay_arg)
                                                        elif action_arg == 'reverse':
                                                            swapper.start_reverse_swap(delay_arg)
                                                        elif action_arg == 'random':
                                                            swapper.start_random_order(delay_arg)
                                                        else:
                                                            logger.error(f'{t_name} Unknown Multicast action e.g random,1000 : {params}')
                                            else:
                                                logger.error(f'{t_name} Not multicast cast')

                                    except Exception as error:
                                        logger.error(traceback.format_exc())
                                        logger.error(f'{t_name} Action {action} in ERROR from {t_name}: {error}')

                                    CASTDesktop.cast_name_todo.remove(item)

                            if len(CASTDesktop.cast_name_todo) == 0:
                                CASTDesktop.t_todo_event.clear()
                            CASTDesktop.t_desktop_lock.release()

                        if t_multicast and (t_cast_y != 1 or t_cast_x != 1):
                            """
                                multicast manage any number of devices of same configuration
                                each device need to drive the same amount of leds, same config
                                e.g. WLED matrix 16x16 : 3(x) x 2(y)                    
                                ==> this give 6 devices to set into cast_devices list                     
                                    (tuple of: device index(0...n) , IP address) 
                                    we will manage image of 3x16 leds for x and 2x16 for y    

                                on 10/04/2024: device_number come from list entry order (0...n)

                            """

                            grid = True

                            # resize frame to virtual matrix size
                            frame_art = CV2Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                            frame = CV2Utils.resize_image(frame,
                                                          self.scale_width * t_cast_x,
                                                          self.scale_height * t_cast_y)

                            if frame_count > 1:
                                # split to matrix
                                t_cast_frame_buffer = Utils.split_image_to_matrix(frame, t_cast_x, t_cast_y)
                                # save frame to np buffer if requested (so can be used after by the main)
                                if self.put_to_buffer and frame_count <= self.frame_max:
                                    self.frame_buffer.append(frame)

                            else:
                                # split to matrix
                                self.cast_frame_buffer = Utils.split_image_to_matrix(frame, t_cast_x, t_cast_y)

                                # validate cast_devices number
                                if len(ip_addresses) != len(self.cast_frame_buffer):
                                    logger.error(
                                        f'{t_name} Cast devices number != sub images number: check cast_devices ')
                                    break

                                t_cast_frame_buffer = self.cast_frame_buffer

                            # send, keep synchronized
                            try:

                                send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                            except Exception as error:
                                logger.error(traceback.format_exc())
                                logger.error(f'{t_name} An exception occurred: {error}')
                                break

                        else:

                            grid = False

                            # resize frame for sending to ddp device
                            frame_to_send = CV2Utils.resize_image(frame, self.scale_width, self.scale_height)
                            # resize frame to pixelart
                            frame = CV2Utils.pixelart_image(frame, self.scale_width, self.scale_height)

                            # DDP run in separate thread to avoid block main loop
                            # here we feed the queue that is read by DDP thread
                            if self.protocol == "ddp":
                                # take only the first
                                if t_multicast is False:
                                    try:
                                        if ip_addresses[0] != '127.0.0.1':
                                            # send data to queue
                                            ddp_host.send_to_queue(frame_to_send, self.retry_number)
                                            CASTDesktop.total_packet += ddp_host.frame_count
                                    except Exception as tr_error:
                                        logger.error(traceback.format_exc())
                                        logger.error(f"{t_name} Exception Error on IP device : {tr_error}")
                                        break

                                # if multicast and more than one ip address and matrix size 1 * 1
                                # we send the frame to all cast devices
                                elif t_multicast is True and t_cast_x == 1 and t_cast_y == 1 and len(ip_addresses) > 1:

                                    t_cast_frame_buffer = [frame_to_send]

                                    # send, keep synchronized
                                    try:

                                        send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                                    except Exception as error:
                                        logger.error(traceback.format_exc())
                                        logger.error(f'{t_name} An exception occurred: {error}')
                                        break

                                # if multicast and only one IP
                                else:
                                    logger.error(f'{t_name} Not enough IP devices defined. Modify Multicast param')
                                    break

                            # save frame to np buffer if requested (so can be used after by the main)
                            if self.put_to_buffer and frame_count <= self.frame_max:
                                self.frame_buffer.append(frame)

                        """
                        Record
                        """
                        if self.record and out_file is not None:
                            out_file.write_frame(frame)

                        """
                        Manage preview window, depend on the platform
                        """
                        # preview on fixed size window
                        if t_preview:

                            if str2bool(app_config['preview_proc']):
                                # for no win platform, cv2.imshow() need to run into Main thread
                                # We use ShareableList to share data between this thread and new process
                                if frame_count == 1:
                                    # create a shared list, name is thread name
                                    try:
                                        sl = ShareableList(
                                            [
                                                CASTDesktop.total_frame,
                                                frame.tobytes(),
                                                self.server_port,
                                                t_viinput,
                                                t_name,
                                                self.preview_top,
                                                t_preview,
                                                self.preview_w,
                                                self.preview_h,
                                                t_todo_stop,
                                                frame_count,
                                                frame_interval,
                                                str(ip_addresses),
                                                self.text,
                                                self.custom_text,
                                                self.cast_x,
                                                self.cast_y,
                                                grid,
                                                str(frame.shape).replace('(', '').replace(')', '')
                                            ],
                                            name=t_name)
                                    except Exception as e:
                                        logger.error(f'{t_name} Exception on shared list creation : {e}')

                                    # run main_preview in another process
                                    # create a child process, so cv2.imshow() will run from its Main Thread
                                    sl_process = Process(target=CV2Utils.sl_main_preview, args=(t_name, 'Desktop',))
                                    # start the child process
                                    # small delay occur, OS take some time to initiate the new process
                                    sl_process.start()
                                    logger.debug(f'Starting Child Process for Preview : {t_name}')

                                # working with the shared list
                                if frame_count > 1:
                                    # what to do from data updated by the child process (keystroke from preview window)
                                    if sl[9] is True or sl[18] == '0,0,0':
                                        t_todo_stop = True
                                    elif sl[6] is False:
                                        t_preview = False
                                    else:
                                        if sl[13] is False:
                                            self.text = False
                                        else:
                                            self.text = True
                                        # Update Data on shared List
                                        sl[0] = CASTDesktop.total_frame
                                        # append not zero value to bytes to solve ShareableList bug
                                        # see https://github.com/python/cpython/issues/106939
                                        new_frame = frame.tobytes()
                                        new_frame = bytearray(new_frame)
                                        new_frame.append(1)
                                        new_frame = bytes(new_frame)
                                        sl[1] = new_frame
                                        #
                                        sl[5] = self.preview_top
                                        sl[7] = self.preview_w
                                        sl[8] = self.preview_h
                                        sl[10] = frame_count
                                        sl[13] = self.text
                                        sl[18] = str(frame.shape).replace('(', '').replace(')', '')

                            else:

                                # for win, not necessary to use child process as this work into thread (avoid overhead)
                                t_preview, t_todo_stop, self.text = CV2Utils.cv2_preview_window(
                                    CASTDesktop.total_frame,
                                    frame,
                                    CASTDesktop.server_port,
                                    t_viinput,
                                    t_name,
                                    self.preview_top,
                                    t_preview,
                                    self.preview_w,
                                    self.preview_h,
                                    t_todo_stop,
                                    frame_count,
                                    frame_interval,
                                    ip_addresses,
                                    self.text,
                                    self.custom_text,
                                    self.cast_x,
                                    self.cast_y,
                                    'Desktop',
                                    grid)

            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error(f'{t_name} An exception occurred: {e}')

            finally:
                """
                END
                """
                # close av input
                input_container.close()
                # close av output if any
                if output_container:
                    # Pass None to the encoder at the end - flush last packets
                    for packet in output_stream.encode(None):
                        output_container.mux(packet)
                        """
                        if self.record:
                            # convert frame to np array
                            frame_np = packet.to_ndarray(format="rgb24")
                            out_file.write_frame(frame_np)
                        """
                    output_container.close()
                # close preview
                if t_preview is True:
                    CV2Utils.cv2_win_close(CASTDesktop.server_port, 'Desktop', t_name, t_viinput)
        else:

            logger.error(f'{t_name} av input_container not defined')

        """
        END +
        """

        CASTDesktop.count -= 1
        CASTDesktop.cast_names.remove(t_name)
        CASTDesktop.t_exit_event.clear()

        # Clean ShareableList
        Utils.sl_clean(sl, sl_process, t_name)

        logger.debug("_" * 50)
        logger.debug(f'Cast {t_name} end using this input: {t_viinput}')
        logger.debug(f'Using these devices: {str(ip_addresses)}')
        logger.debug("_" * 50)

        logger.info(f'{t_name} Cast closed')

    def cast(self, shared_buffer=None, log_ui=None):
        """
            this will run the cast into another thread
            avoiding blocking the main one
            this will also populate windows titles in case of
            shared_buffer: if used need to be a queue
            log_ui : logger to send data to main logger on root page
        """
        if log_ui is not None:
            root_logger = logging.getLogger()
            if log_ui not in root_logger:
                logger.addHandler(log_ui)
        thread = threading.Thread(target=self.t_desktop_cast, args=(shared_buffer,))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        self.all_windows_titles = Utils.windows_titles()
        logger.debug('Child Desktop cast initiated')



