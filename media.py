# a: zak-45
# d: 13/03/2024
# v: 1.0.0
#
# CASTMedia class
#
#           Cast your media to ddp device (e.g.WLED)
#                     
#
# This utility aim to be cross-platform.
# You can cast an image file , a video file, or a capture device (USB camera ...)
# Data will be sent through 'ddp' protocol
# ddp data are sent by using queue feature to avoid any network problem which cause latency
# A preview can be seen via 'cv2' : pixelart look
#
# in case of camera status() timeout in linux
# camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
# 27/05/2024: cv2.imshow with import av  freeze
#


import logging
import logging.config
import sys
import traceback
import numpy as np

import cv2
import time
import os

import cfg_load as cfg
from str2bool import str2bool

import threading
from threading import current_thread

import asyncio
import concurrent.futures

from ddp_queue import DDPDevice
from utils import CASTUtils as Utils, ImageUtils


"""
When this env var exist, this mean run from the one-file executable.
Load of the config is not possible, folder config should not exist.
This avoid FileNotFoundError.
This env not exist when run the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    # read log config
    logging.config.fileConfig('config/logging.ini')
    # create logger
    logger = logging.getLogger('WLEDLogger.media')

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


class CASTMedia:
    """ Cast Media to DDP """

    count = 0  # initialise running casts count to zero
    total_frame = 0  # total number of processed frames

    cast_names = []  # should contain running Cast instances
    cast_name_todo = []  # list of cast names with action that need to execute from 'to do'

    t_exit_event = threading.Event()  # thread listen event fo exit
    t_todo_event = threading.Event()  # thread listen event for task to do

    t_media_lock = threading.Lock()  # define lock for to do

    server_port = Utils.get_server_port()

    total_packet = 0  # net packets number

    def __init__(self):
        self.rate: int = 25
        self.stopcast: bool = True
        self.preview_top: bool = False
        self.preview_w: int = 640
        self.preview_h: int = 360
        self.scale_width: int = 128
        self.scale_height: int = 128
        self.wled: bool = False
        self.wled_live = False
        self.host: str = "127.0.0.1"
        self.port: int = 4048
        self.protocol: str = "ddp"
        self.retry_number: int = 0
        self.viinput: int = 0
        self.keep_ratio: bool = True
        self.flip: bool = False
        self.flip_vh: int = 0  # 0 , 1
        self.saturation = 0
        self.brightness = 0
        self.contrast = 0
        self.sharpen = 0
        self.balance_r = 0
        self.balance_g = 0
        self.balance_b = 0
        self.auto_bright = False
        self.clip_hist_percent = 25
        self.gamma = 0.5
        self.frame_buffer = []
        self.frame_index: int = 0
        self.put_to_buffer: bool = False
        self.frame_max: int = 8
        self.text: bool = cfg_text
        self.custom_text: str = ""
        self.multicast: bool = False
        self.cast_x: int = 1
        self.cast_y: int = 1
        self.cast_devices: list = []
        self.cast_frame_buffer = []
        self.ddp_multi_names = []
        self.force_mjpeg = False
        self.cast_skip_frames: int = 0
        self.player_time: float = 0
        self.player_duration: float = 0
        self.player_sync = False
        self.auto_sync = False
        self.auto_sync_delay: int = 30
        self.reset_total = False

        if sys.platform.lower() == 'win32':
            self.preview = True
        elif sys.platform.lower() == 'linux':
            self.preview = False
        elif sys.platform.lower() == 'darwin':
            self.preview = False
        else:
            self.preview = False

    """
    Cast Thread
    """

    def t_media_cast(self, shared_buffer=None):
        """
            Main cast logic
            Cast media : video file, image file or video capture device
        """

        t_name = current_thread().name
        if CASTMedia.count == 0 or self.reset_total is True:
            CASTMedia.total_frame = 0
            CASTMedia.total_packet = 0

        logger.info(f'Child thread: {t_name}')

        t_send_frame = threading.Event()  # thread listen event to send frame via ddp (for synchro used by multicast)

        start_time = time.time()
        t_preview = self.preview
        t_multicast = self.multicast
        t_cast_x = self.cast_x
        t_cast_y = self.cast_y
        t_cast_frame_buffer = []

        frame_count = 0

        delay: float = 0
        if self.rate != 0:
            delay: float = 1.0 / self.rate  # Calculate the time interval between frames

        t_todo_stop = False

        """
        Cast devices
        """

        ip_addresses = []

        """
        viinput can be:

            name of video file (eg. video.avi) 
            or image sequence (eg. img_%02d.jpg, which will read samples like img_00.jpg, img_01.jpg, img_02.jpg, ...) 
            or URL of video stream (eg. protocol://host:port/script_name?script_params|auth) 
            or GStreamer pipeline string in gst-launch tool format in case if GStreamer is used as backend 
            Note that each video stream or IP camera feed has its own URL scheme. 
            Please refer to the documentation of source stream to know the right URL.

        """

        if str(self.viinput) == "":
            logger.error('Filename could not be empty')
            return False

        t_viinput = self.viinput

        """
        MultiCast inner function protected from what happens outside.
        """

        def send_multicast_image(ip, image):
            """
            This sends an image to an IP address using DDP, used by multicast
            :param ip:
            :param image:
            :return:
            """
            # timeout provided to not have thread waiting infinitely
            if t_send_frame.wait(timeout=.2):
                # send ddp data, we select DDPDevice based on the IP
                for device in self.ddp_multi_names:
                    if ip == device.name:
                        device.send_to_queue(image, self.retry_number)
                        CASTMedia.total_packet += device.frame_count
                        break
            else:
                logger.warning('Multicast frame dropped')

        def send_multicast_images_to_ips(images_buffer, to_ip_addresses):
            """
            Create a thread for each image , IP pair and wait for all to finish
            Very simple synchro process
            :param to_ip_addresses:
            :param images_buffer:
            :return:
            """
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Submit a thread for each image and IP pair
                multicast = [executor.submit(send_multicast_image, ip, image)
                             for ip, image in zip(to_ip_addresses, images_buffer)]

                # once all threads up, need to set event because they wait for
                t_send_frame.set()

                # Wait for all threads to complete, let 1 second
                concurrent.futures.wait(multicast, timeout=1)

            t_send_frame.clear()

        """
        End Multicast
        """

        """
        First, check devices 
        """

        ddp_host = None
        # check IP
        if self.host != '127.0.0.1':  # 127.0.0.1 should always exist
            if Utils.check_ip_alive(self.host):
                logger.info(f'We work with this IP {self.host} as first device: number 0')
            else:
                logger.error(f'Error looks like IP {self.host} do not accept connection to port 80')
                return False

            ddp_host = DDPDevice(self.host)  # init here as queue thread not necessary if 127.0.0.1

        # retrieve matrix setup from wled and set w/h
        if self.wled:
            status = asyncio.run(Utils.put_wled_live(self.host, on=True, live=True, timeout=1))
            if status:
                self.scale_width, self.scale_height = asyncio.run(Utils.get_wled_matrix_dimensions(self.host))
            else:
                logger.error(f"ERROR to set WLED device {self.host} on 'live' mode")
                return False

        # specifics to Multicast
        if t_multicast:
            # validate cast_devices list
            if not Utils.is_valid_cast_device(str(self.cast_devices)):
                logger.error("Error Cast device list not compliant to format [(0,'xx.xx.xx.xx')...]")
                return False
            else:
                logger.info('Virtual Matrix size is :' +
                            str(self.scale_width * t_cast_x) + 'x' + str(self.scale_height * t_cast_y))
                # populate ip_addresses list
                for i in range(len(self.cast_devices)):
                    cast_ip = self.cast_devices[i][1]
                    valid_ip = Utils.check_ip_alive(cast_ip, port=80, timeout=2)
                    if valid_ip:
                        if self.wled:
                            status = asyncio.run(Utils.put_wled_live(cast_ip, on=True, live=True, timeout=1))
                            if not status:
                                logger.error(f"ERROR to set WLED device {self.host} on 'live' mode")
                                return False

                        ip_addresses.append(cast_ip)
                        # create ddp device for each IP
                        self.ddp_multi_names.append(DDPDevice(cast_ip))
                        logger.info(f'IP : {cast_ip} for sub image number {i}')
                    else:
                        logging.error(f'Not able to validate ip : {cast_ip}')
        else:

            ip_addresses.append(self.host)

        """
        Second, capture media
        """
        frame = None
        self.frame_buffer = []
        self.cast_frame_buffer = []

        # capture media
        media = cv2.VideoCapture(t_viinput)
        # Check if the capture is successful
        if not media.isOpened():
            logger.error(f"Error: Unable to open media stream {t_viinput}.")
            return False

        # retrieve frame count, if 1 we assume image (should be no?)
        length = int(media.get(cv2.CAP_PROP_FRAME_COUNT))
        if length == 1:
            media = cv2.imread(str(t_viinput))
            frame = media
            fps = 1
        else:
            fps = media.get(cv2.CAP_PROP_FPS)
            media.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if self.force_mjpeg:
                media.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))

        # Calculate the interval between frames in seconds
        if self.rate != 0:
            interval: float = 1.0 / self.rate
        else:
            logger.error('Rate could not be zero')
            return False

        logger.info(f"Playing media {t_viinput} of length {length} at {fps} FPS")
        logger.info(f"Stopcast value : {self.stopcast}")

        # detect if we want specific frame index: only for non-live video
        if self.frame_index != 0 and length > 1:
            logger.info(f"Take frame number {self.frame_index}")
            media.set(1, self.frame_index - 1)

        CASTMedia.cast_names.append(t_name)
        CASTMedia.count += 1

        logger.info('Cast running ...')

        """
            Media Loop
        """
        # Main thread loop to read media frame, stop from global call or local
        while not (self.stopcast or t_todo_stop):
            """
            instruct the thread to exit 
            """
            if CASTMedia.t_exit_event.is_set():
                break

            # Calculate the expected time for the current frame
            expected_time = start_time + frame_count * interval

            #  read media
            if length != 1:
                if self.cast_skip_frames != 0:
                    frame_number = frame_count + self.cast_skip_frames
                    media.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
                    self.cast_skip_frames = 0
                else:
                    if self.player_sync:
                        media.set(cv2.CAP_PROP_POS_MSEC, self.player_time)
                        self.player_sync = False
                        logger.info(f'Sync Cast to time :{self.player_time}')
                    else:
                        if self.auto_sync:
                            # sync every x seconds, 5  sec first time
                            if ((frame_count % (self.rate * self.auto_sync_delay) == 0 or
                                 (frame_count == (self.rate * 5)) and
                                    self.player_time != 0 and
                                    frame_count > 0)):
                                time_to_set = self.player_time
                                media.set(cv2.CAP_PROP_POS_MSEC, time_to_set)
                                logger.info(f'Auto Sync Cast to time :{time_to_set}')

                success, frame = media.read()
                if not success:
                    if frame_count != length:
                        logger.warning('Not all frames have been read')
                    else:
                        logger.info('Media reached END')
                    break

            # convert to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # adjust gamma
            frame = cv2.LUT(frame, ImageUtils.gamma_correct_frame(self.gamma))
            # auto brightness / contrast
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

            if CASTMedia.t_todo_event.is_set():
                logger.debug(f"We are inside todo :{CASTMedia.cast_name_todo}")
                CASTMedia.t_media_lock.acquire()
                #  take thread name from cast to do list
                for item in CASTMedia.cast_name_todo:
                    name, action, added_time = item.split('||')

                    if name not in CASTMedia.cast_names:
                        CASTMedia.cast_name_todo.remove(item)

                    elif name == t_name:
                        logging.debug(f'To do: {action} for :{t_name}')

                        # use try to capture any failure
                        try:
                            if 'stop' in action:
                                t_todo_stop = True
                            elif 'shot' in action:
                                add_frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                                add_frame = Utils.resize_image(add_frame, self.scale_width, self.scale_height)
                                self.frame_buffer.append(add_frame)
                                if t_multicast:
                                    # resize frame to virtual matrix size
                                    add_frame = Utils.resize_image(frame,
                                                                   self.scale_width * t_cast_x,
                                                                   self.scale_height * t_cast_y)

                                    self.cast_frame_buffer = Utils.split_image_to_matrix(add_frame,
                                                                                         t_cast_x, t_cast_y)
                            elif 'info' in action:
                                t_info = {t_name: {"type": "info", "data": {"start": start_time,
                                                                            "tid": current_thread().native_id,
                                                                            "viinput": str(t_viinput),
                                                                            "preview": t_preview,
                                                                            "multicast": t_multicast,
                                                                            "devices": ip_addresses,
                                                                            "fps": 1 / delay,
                                                                            "frames": frame_count,
                                                                            "length": length
                                                                            }
                                                   }
                                          }
                                # this wait until queue access is free
                                shared_buffer.put(t_info)
                                logger.debug('we have put')

                            elif 'close_preview' in action:
                                window_name = (f"{CASTMedia.server_port}-Media Preview input: " +
                                               str(t_viinput) + str(t_name))
                                win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                                if not win == 0:
                                    cv2.destroyWindow(window_name)
                                t_preview = False

                            elif 'open_preview' in action:
                                t_preview = True

                            elif "reset" in action:
                                CASTMedia.total_frame = 0
                                CASTMedia.total_packet = 0
                                self.reset_total = False

                        except Exception as error:
                            logger.error(traceback.format_exc())
                            logger.error(f'Action {action} in ERROR from {t_name} : {error}')

                        CASTMedia.cast_name_todo.remove(item)

                if len(CASTMedia.cast_name_todo) == 0:
                    CASTMedia.t_todo_event.clear()
                CASTMedia.t_media_lock.release()

            if t_multicast:
                """
                    multicast manage any number of devices of same configuration
                    each device need to drive the same amount of leds, same config
                    e.g. WLED matrix 16x16 : 3(x) x 2(y)                    
                    ==> this give 6 devices to set into cast_devices list                         
                        (tuple of: device index(0...n) , IP address) 
                        we will manage image of 3x16 leds for x and 2x16 for y    
                        
                    on 10/04/2024: device_number come from list entry order (0...n)
                        
                """

                # resize frame to virtual matrix size
                frame_art = Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                frame = Utils.resize_image(frame,
                                           self.scale_width * t_cast_x,
                                           self.scale_height * t_cast_y)

                # populate global cast buffer from first frame only
                if frame_count > 1:
                    # split to matrix
                    t_cast_frame_buffer = Utils.split_image_to_matrix(frame, t_cast_x, t_cast_y)
                    # put frame to np buffer (so can be used after by the main)
                    if self.put_to_buffer and frame_count <= self.frame_max:
                        add_frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                        add_frame = Utils.resize_image(add_frame, self.scale_width, self.scale_height)
                        self.frame_buffer.append(add_frame)

                else:
                    # split to matrix
                    self.cast_frame_buffer = Utils.split_image_to_matrix(frame, t_cast_x, t_cast_y)
                    # validate cast_devices number
                    if len(ip_addresses) < len(self.cast_frame_buffer):
                        logger.error('Cast devices number != sub images number: check cast_devices ')
                        break
                    t_cast_frame_buffer = self.cast_frame_buffer

                # send, keep synchronized
                try:

                    send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                except Exception as error:
                    logger.error(traceback.format_exc())
                    logger.error(f'An exception occurred: {error}')
                    break

                if t_preview:
                    t_preview = self.preview_window(frame_art,
                                                    CASTMedia.server_port,
                                                    t_viinput,
                                                    t_name,
                                                    t_preview,
                                                    frame_count,
                                                    interval,
                                                    grid=True)

                if length == 1 and fps == 1:
                    break

            else:

                # resize frame for sending to ddp device
                frame_to_send = Utils.resize_image(frame, self.scale_width, self.scale_height)
                # resize frame to pixelart
                frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)

                # send to DDP : run in separate thread to avoid block main loop
                if self.protocol == "ddp" and ip_addresses[0] != '127.0.0.1':
                    # send data to queue
                    ddp_host.send_to_queue(frame_to_send, self.retry_number)
                    CASTMedia.total_packet += ddp_host.frame_count

                # put frame to np buffer (so can be used after by the main)
                if self.put_to_buffer and frame_count <= self.frame_max:
                    add_frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                    add_frame = Utils.resize_image(add_frame, self.scale_width, self.scale_height)
                    self.frame_buffer.append(add_frame)

                # preview on fixed size window
                if t_preview:
                    t_preview = self.preview_window(frame,
                                                    CASTMedia.server_port,
                                                    t_viinput,
                                                    t_name,
                                                    t_preview,
                                                    frame_count,
                                                    interval
                                                    )

                """
                    stop for non-live video (length not -1)
                    if we reach end of video or request only one frame from index
                """
                if length != -1:
                    if frame_count >= length or self.frame_index != 0:
                        logger.info("Reached END ...")
                        break

            """
            do we need to sleep.
            """
            if CASTMedia.t_todo_event.is_set():
                pass
            else:
                # Calculate the current time
                current_time = time.time()

                # Calculate the time to sleep to maintain the desired FPS
                sleep_time = expected_time - current_time

                if sleep_time > 0:
                    time.sleep(sleep_time)

            frame_count += 1
            CASTMedia.total_frame += 1

        """
            Final : End Media Loop
        """

        CASTMedia.count -= 1
        CASTMedia.cast_names.remove(t_name)
        CASTMedia.t_exit_event.clear()

        if CASTMedia.count <= 2 and t_preview is True:  # try to avoid blocking when click as a bad man !!!
            logger.info('Stop window preview if any')
            window_name = f"{CASTMedia.server_port}-Media Preview input: " + str(t_viinput) + str(t_name)
            win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
            if not win == 0:
                cv2.destroyWindow(window_name)

        if not isinstance(media, np.ndarray):
            logger.info('Release Media')
            media.release()

        logger.info("_" * 50)
        logger.info(f'Cast {t_name} end using this media: {t_viinput}')
        logger.info(f'Using these devices: {str(ip_addresses)}')
        logger.info("_" * 50)

        logger.info("Cast closed")

    """
    preview window
    """

    def preview_window(self, frame, server_port, t_viinput, t_name, t_preview, frame_count, fps, grid=False):

        frame = cv2.resize(frame, (self.preview_w, self.preview_h))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # put text on the image
        if self.text:
            if self.custom_text == "":
                text_to_show = f"WLEDVideoSync: {server_port} - "
                text_to_show += "FPS: " + str(1/fps) + " - "
                text_to_show += "FRAME: " + str(frame_count) + " - "
                text_to_show += "TOTAL: " + str(CASTMedia.total_frame)
            else:
                text_to_show = self.custom_text
            # font
            font = cv2.FONT_HERSHEY_SIMPLEX
            # org
            org = (50, 50)
            x, y, w, h = 40, 15, 560, 40
            # Draw black background rectangle
            cv2.rectangle(frame, (x, x), (x + w, y + h), (0, 0, 0), -1)
            # fontScale
            fontscale = .4
            # Blue color in BGR
            color = (255, 255, 255)
            # Line thickness of 2 px
            thickness = 1
            # Using cv2.putText() method
            frame = cv2.putText(frame,
                                text_to_show,
                                org,
                                font,
                                fontscale,
                                color,
                                thickness,
                                cv2.LINE_AA)

        # Displaying the image
        window_name = f"{server_port}-Media Preview input: " + str(t_viinput) + str(t_name)
        if grid:
            frame = ImageUtils.grid_on_image(frame, self.cast_x, self.cast_y)

        cv2.imshow(window_name, frame)
        cv2.resizeWindow(window_name, self.preview_w, self.preview_h)

        top = 0
        if self.preview_top is True:
            top = 1
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, top)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
            if not win == 0:
                cv2.destroyWindow(window_name)
            t_preview = False

        return t_preview

    def cast(self, shared_buffer=None):
        """
            this will run the cast into another thread
            avoid to block the main one
            shared_buffer: if used need to be a queue
        """
        thread = threading.Thread(target=self.t_media_cast, args=(shared_buffer,))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        logger.info('Child Media cast initiated')
