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
# 27/05/2024: cv2.imshow with import av  freeze on OS not Win
# to fix it, cv2.imshow can run from its own process with cost of additional overhead, set preview_proc = True
#

import sys
import os

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

import asyncio
import concurrent.futures

from ddp_queue import DDPDevice
from utils import CASTUtils as Utils
from cv2utils import CV2Utils, ImageUtils

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
        self.voformat: str = 'h264'
        self.vooutput: str = 'udp://127.0.0.1:12345?pkt_size=1316'
        self.put_to_buffer: bool = False
        self.frame_buffer: list = []
        self.frame_max: int = 8
        self.multicast: bool = False
        self.cast_x: int = 1
        self.cast_y: int = 1
        self.cast_devices: list = []
        self.cast_frame_buffer = []
        self.ddp_multi_names = []
        self.monitor_number: int = 0  # monitor to use for area selection
        self.screen_coordinates = []
        self.reset_total = False
        self.preview = True

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

    def t_desktop_cast(self, shared_buffer=None):
        """
            Cast desktop screen or a window content based on the title
        """

        import av

        t_name = threading.current_thread().name
        if CASTDesktop.count == 0 or self.reset_total is True:
            CASTDesktop.total_frame = 0
            CASTDesktop.total_packet = 0

        logger.info(f'Child thread: {t_name}')

        t_send_frame = threading.Event()  # thread listen event to send frame via ddp, for multicast synchro

        start_time = time.time()
        t_preview = self.preview
        t_multicast = self.multicast
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
                for device in self.ddp_multi_names:
                    if ip == device.name:
                        device.send_to_queue(image, self.retry_number)
                        CASTDesktop.total_packet += device.frame_count
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

        # check IP
        if self.host != '127.0.0.1':  # 127.0.0.1 should always exist
            if Utils.check_ip_alive(self.host):
                logger.info(f'{t_name} We work with this IP {self.host} as first device: number 0')
            else:
                logger.error(f'{t_name} Error looks like IP {self.host} do not accept connection to port 80')
                return False

            ddp_host = DDPDevice(self.host)  # init here as queue thread not necessary if 127.0.0.1

        # retrieve matrix setup from wled and set w/h
        if self.wled:
            status = asyncio.run(Utils.put_wled_live(self.host, on=True, live=True, timeout=1))
            if status:
                self.scale_width, self.scale_height = asyncio.run(Utils.get_wled_matrix_dimensions(self.host))
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
                            status = asyncio.run(Utils.put_wled_live(cast_ip, on=True, live=True, timeout=1))
                            if not status:
                                logger.error(f"{t_name} ERROR to set WLED device {self.host} on 'live' mode")
                                return False

                        ip_addresses.append(cast_ip)
                        # create ddp device for each IP
                        self.ddp_multi_names.append(DDPDevice(cast_ip))
                        logger.info(f'{t_name} IP : {cast_ip} as device number {i}')
                    else:
                        logging.error(f'{t_name} Not able to validate ip : {cast_ip}')
        else:

            ip_addresses.append(self.host)

        """
        Second, capture media
        """

        self.frame_buffer = []
        self.cast_frame_buffer = []
        frame_interval = self.rate

        # Open video device (desktop / window)
        input_options = {'c:v': 'libx264rgb', 'crf': '0', 'preset': 'ultrafast', 'pix_fmt': 'rgb24',
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

        input_format = self.viformat

        """
        viinput can be:
                    desktop : to stream full screen or a part of the screen
                    title=<window name> : to stream only window content                    
                    or str
        """

        if self.viinput in ['desktop', 'area'] and sys.platform.lower() == 'win32':
            t_viinput = 'desktop'
        elif self.viinput in ['area'] and sys.platform.lower() == 'linux':
            t_viinput = os.getenv('DISPLAY')
        else:
            t_viinput = self.viinput

        # Open av input container in read mode
        try:

            input_container = av.open(t_viinput, 'r', format=input_format, options=input_options)

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'{t_name} An exception occurred: {error}')
            return False

        # Define Output via av only if protocol is other
        if 'other' in self.protocol:
            try:

                # Output video in case of UDP or other
                output_options = {}
                output_format = self.voformat
                output_filename = self.vooutput

                output_container = av.open(output_filename, 'w', format=output_format)
                output_stream = output_container.add_stream('h264', rate=self.rate, options=output_options)
                output_stream.thread_type = "AUTO"

            except Exception as error:
                logger.error(traceback.format_exc())
                logger.error(f'{t_name} An exception occurred: {error}')
                return False

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
                logger.info(f"{t_name} Stopcast value : {self.stopcast}")

                for frame in input_container.decode(input_stream):

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
                        # Encode the frame
                        packet = output_stream.encode(frame)
                        # Mux the encoded packet
                        output_container.mux(packet)

                    else:

                        # resize to default size
                        frame = frame.reformat(640, 360)

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
                                name, action, added_time = item.split("||")

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

                                    except Exception as error:
                                        logger.error(traceback.format_exc())
                                        logger.error(f'{t_name} Action {action} in ERROR from {t_name}: {error}')

                                    CASTDesktop.cast_name_todo.remove(item)

                            if len(CASTDesktop.cast_name_todo) == 0:
                                CASTDesktop.t_todo_event.clear()
                            CASTDesktop.t_desktop_lock.release()

                        if t_multicast and (t_cast_y != 1 and t_cast_x != 1):
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
                                if ip_addresses[0] != '127.0.0.1' and len(ip_addresses) == 1:
                                    # send data to queue
                                    ddp_host.send_to_queue(frame_to_send, self.retry_number)
                                    CASTDesktop.total_packet += ddp_host.frame_count

                                    # if multicast and more than one ip address and matrix size 1 * 1
                                    # we send the frame to all cast devices
                                elif len(ip_addresses) > 1 and t_multicast is True and t_cast_x == 1 and t_cast_y == 1:

                                    t_cast_frame_buffer.append(frame_to_send)

                                    # send, keep synchronized
                                    try:

                                        send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                                    except Exception as error:
                                        logger.error(traceback.format_exc())
                                        logger.error(f'{t_name} An exception occurred: {error}')
                                        break

                                    CASTDesktop.total_packet += ddp_host.frame_count

                            # save frame to np buffer if requested (so can be used after by the main)
                            if self.put_to_buffer and frame_count <= self.frame_max:
                                self.frame_buffer.append(frame)

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
                                            self.rate,
                                            str(ip_addresses),
                                            self.text,
                                            self.custom_text,
                                            self.cast_x,
                                            self.cast_y,
                                            grid,
                                            str(frame.shape).replace('(', '').replace(')', '')
                                        ],
                                        name=t_name)

                                    # run main_preview in another process
                                    # create a child process, so cv2.imshow() will run from its Main Thread
                                    sl_process = Process(target=CV2Utils.sl_main_preview, args=(t_name, 'Desktop',))
                                    # start the child process
                                    # small delay occur, OS take some time to initiate the new process
                                    sl_process.start()
                                    logger.info(f'Starting Child Process for Preview : {t_name}')

                                # working with the shared list
                                if frame_count > 1:
                                    # what to do from data updated by the child process
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
                                    self.rate,
                                    ip_addresses,
                                    self.text,
                                    self.custom_text,
                                    self.cast_x,
                                    self.cast_y,
                                    'Desktop',
                                    grid)

            except Exception as error:
                logger.error(traceback.format_exc())
                logger.error(f'{t_name} An exception occurred: {error}')

            finally:
                """
                END
                """
                # close av input
                input_container.close()
                # close av output if any
                if output_container:
                    output_container.close()
                if t_preview is True:
                    CV2Utils.cv2_win_close(CASTDesktop.server_port, 'Desktop', t_name, t_viinput)
        else:

            logger.warning(f'{t_name} av input_container not defined')

        """
        END +
        """

        CASTDesktop.count -= 1
        CASTDesktop.cast_names.remove(t_name)
        CASTDesktop.t_exit_event.clear()

        # Clean ShareableList
        Utils.sl_clean(sl, sl_process, t_name)

        logger.info("_" * 50)
        logger.info(f'Cast {t_name} end using this input: {t_viinput}')
        logger.info(f'Using these devices: {str(ip_addresses)}')
        logger.info("_" * 50)

        logger.info(f'{t_name} Cast closed')

    def cast(self, shared_buffer=None, log_ui=None):
        """
            this will run the cast into another thread
            avoiding blocking the main one
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
        logger.info('Child Desktop cast initiated')
