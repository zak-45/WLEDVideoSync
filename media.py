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
import concurrent_log_handler

from multiprocessing.shared_memory import ShareableList
import traceback
import numpy as np

import cv2
import time
import os

import cfg_load as cfg
from str2bool import str2bool

import threading

from asyncio import run
import concurrent.futures

from ddp_queue import DDPDevice
from utils import CASTUtils as Utils
from cv2utils import CV2Utils, ImageUtils

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
    logger = Utils.setup_logging('config/logging.ini', 'WLEDLogger.media')

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
    cast_name_to_sync = []  # list of cast names to sync time

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
        self.force_mjpeg = False  # force cv2 to use this format, webcam help on linux
        self.cast_skip_frames: int = 0  # at cast init , number of frame to skip before start read
        self.sync_to_time: float = 0  # time retrieved from the video or slider
        self.player_duration: float = 0  # play time of the video
        self.cast_sync = False  # do we want to sync
        self.all_sync = False  # sync all running casts
        self.auto_sync = False  # automatic sync depend on the delay
        self.auto_sync_delay: int = 30  # delay for auto sync
        self.add_all_sync_delay = 0  # additional time to add to player_time during all sync +/-
        self.cast_sleep = False  # instruct cast to wait until all sync
        self.reset_total = False  # reset total number of frame / packets on monitor
        self.preview = True
        self.repeat = 0  # number of repetition, from -1 to 9999,  -1 = infinite

    """
    Cast Thread
    """

    def t_media_cast(self, shared_buffer=None):
        """
            Main cast logic
            Cast media : video file, image file or video capture device
        """

        t_name = threading.current_thread().name
        if CASTMedia.count == 0 or self.reset_total is True:
            CASTMedia.total_frame = 0
            CASTMedia.total_packet = 0

        logger.debug(f'Child thread: {t_name}')

        t_send_frame = threading.Event()  # thread listen event to send frame via ddp (for synchro used by multicast)

        start_time = time.time()
        t_preview = self.preview
        t_multicast = self.multicast
        t_ddp_multi_names =[]
        t_cast_x = self.cast_x
        t_cast_y = self.cast_y
        t_cast_frame_buffer = []

        frame_count = 0

        t_todo_stop = False

        self.cast_sync = False
        self.cast_sleep = False
        CASTMedia.cast_name_to_sync = []

        sl_process = None
        sl = None

        t_repeat = self.repeat

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
            logger.error(f'{t_name} Filename could not be empty')
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
            if t_send_frame.wait(timeout=.5):
                # send ddp data, we select DDPDevice based on the IP
                for dev in t_ddp_multi_names:
                    if ip == dev._destination:
                        dev.send_to_queue(image, self.retry_number)
                        CASTMedia.total_packet += dev.frame_count
                        break
            else:
                logger.warning(f'{t_name} Multicast frame dropped')

        def send_multicast_images_to_ips(images_buffer, to_ip_addresses):
            """
            Create a thread for each image , IP pair and wait for all to finish
            Very simple synchro process
            :param to_ip_addresses:
            :param images_buffer:
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
            if status is True:
                self.scale_width, self.scale_height = run(Utils.get_wled_matrix_dimensions(self.host))
            else:
                logger.error(f"{t_name} ERROR to set WLED device {self.host} on 'live' mode")
                return False

        # specifics to Multicast
        if t_multicast:
            # validate cast_devices list
            if not Utils.is_valid_cast_device(str(self.cast_devices)):
                logger.error(f"{t_name} Error Cast device list not compliant to format [(0,'xx.xx.xx.xx')...]")
                return False
            else:
                logger.info(f'{t_name} Virtual Matrix size is :' +
                            str(self.scale_width * t_cast_x) + 'x' + str(self.scale_height * t_cast_y))
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

            ip_addresses=[self.host]

        """
        Second, capture media
        """
        frame = None
        orig_frame = None
        is_image = False
        self.frame_buffer = []
        self.cast_frame_buffer = []

        # capture media
        media = cv2.VideoCapture(t_viinput)
        # Check if the capture is successful
        if not media.isOpened():
            logger.error(f"{t_name} Error: Unable to open media stream {t_viinput}.")
            return False

        # retrieve frame count, if 1 we assume image (should be no?)
        media_length = int(media.get(cv2.CAP_PROP_FRAME_COUNT))
        if media_length == 1:
            media.release()
            media = cv2.imread(str(t_viinput))
            frame = media
            orig_frame = frame
            fps = 1
            is_image = True
        else:
            fps = media.get(cv2.CAP_PROP_FPS)
            media.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if self.force_mjpeg:
                media.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))

        # Calculate the interval between frames in seconds (fps)
        if self.rate != 0:
            interval: float = 1.0 / self.rate
        else:
            logger.error(f'{t_name} Rate could not be zero')
            return False

        logger.info(f"{t_name} Playing media {t_viinput} of length {media_length} at {fps} FPS")
        logger.debug(f"{t_name} Stopcast value : {self.stopcast}")

        # detect if we want specific frame index: only for non-live video (-1) and not image (1)
        if self.frame_index != 0 and media_length > 1:
            logger.debug(f"{t_name} Start at frame number {self.frame_index}")
            media.set(cv2.CAP_PROP_POS_FRAMES, self.frame_index - 1)

        CASTMedia.cast_names.append(t_name)
        CASTMedia.count += 1

        # Calculate the current time
        current_time = time.time()
        auto_expected_time = current_time

        logger.debug(f'{t_name} Cast running ...')

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

            #
            #  read media
            #

            # media is video or live
            if media_length != 1:
                # only for video
                if media_length > 1:
                    # Sync all casts to player_time if requested
                    # manage concurrent access to the list by using lock feature
                    # set value if auto sync is true
                    if self.auto_sync is True:
                        # sync every x seconds
                        if current_time - auto_expected_time >= self.auto_sync_delay:
                            time_to_set = self.sync_to_time
                            self.cast_sync = True
                            logger.debug(f"{t_name}  Name to sync  :{CASTMedia.cast_name_to_sync}")

                            CASTMedia.t_media_lock.acquire()
                            if self.all_sync is True and len(CASTMedia.cast_name_to_sync) == 0:
                                # populate cast names to sync
                                CASTMedia.cast_name_to_sync = CASTMedia.cast_names.copy()
                                # add additional time, can help if cast number > 0 to try to avoid small decay
                                time_to_set += self.add_all_sync_delay
                                logger.debug(f"{t_name}  Got these to sync from auto :{CASTMedia.cast_name_to_sync}")
                            CASTMedia.t_media_lock.release()

                            auto_expected_time = current_time
                            logger.debug(f'{t_name} Auto Sync Cast to time :{time_to_set}')

                    if self.all_sync is True and self.cast_sync is True:

                        CASTMedia.t_media_lock.acquire()

                        # populate cast names to sync if necessary
                        if len(CASTMedia.cast_name_to_sync) == 0 and self.auto_sync is False:
                            CASTMedia.cast_name_to_sync = CASTMedia.cast_names.copy()
                            logger.debug(f"{t_name}  Got these to sync  :{CASTMedia.cast_name_to_sync}")

                        # take only cast not already synced
                        if t_name in CASTMedia.cast_name_to_sync:
                            self.cast_sleep = True
                            # remove thread name from cast to sync list
                            logging.debug(f"{t_name} remove from all sync")
                            CASTMedia.cast_name_to_sync.remove(t_name)
                            # sync cast
                            media.set(cv2.CAP_PROP_POS_MSEC, self.sync_to_time)
                            logger.debug(f'{t_name} ALL Sync Cast to time :{self.sync_to_time}')

                            logger.debug(f'{t_name} synced')

                            # if no more, reset all_sync
                            if len(CASTMedia.cast_name_to_sync) == 0:
                                if self.auto_sync is False:
                                    self.all_sync = False
                                self.cast_sync = False
                                self.cast_sleep = False
                                logger.debug(f"{t_name} All sync finished")

                        CASTMedia.t_media_lock.release()

                        logger.debug(f'{t_name} go to sleep if necessary')
                        while (self.cast_sleep is True and
                               self.cast_sync is True and
                               len(CASTMedia.cast_name_to_sync) > 0):
                            # sleep until all remaining casts sync
                            time.sleep(.001)
                        logger.debug(f"{t_name} exit sleep")

                    else:

                        if self.cast_skip_frames != 0:
                            # this work only for the first cast that read the value
                            frame_number = frame_count + self.cast_skip_frames
                            media.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
                            self.cast_skip_frames = 0
                        else:
                            # this work only for the first cast that read the value
                            if self.cast_sync:
                                media.set(cv2.CAP_PROP_POS_MSEC, self.sync_to_time)
                                self.cast_sync = False
                                logger.debug(f'{t_name} Sync Cast to time :{self.sync_to_time}')
                #
                # read frame for all
                #
                success, frame = media.read()
                if not success:
                    if frame_count != media_length:
                        logger.warning(f'{t_name} Not all frames have been read')
                        break

                    else:
                        logger.debug(f'{t_name} Media reached END')
                        # manage the repeat feature, if -1 then unlimited
                        if t_repeat > 0 or t_repeat < 0:
                            t_repeat -= 1
                            logger.debug(f'{t_name} Remaining repeat : {t_repeat}')
                            # reset media to start
                            media.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            # read one frame
                            success, frame = media.read()
                            if not success:
                                logger.error(f'{t_name} Not able to repeat')
                                break
                            frame_count = 0
                            # reset start time to be able to calculate sleep time to reach requested fps
                            start_time = time.time()
                            # Calculate the current time
                            current_time = time.time()
                            auto_expected_time = current_time

                        else:
                            break

            # resize to default
            # this will validate media passed to cv2
            # common part for image media_length = 1 or live video = -1 or video > 1
            # break in case of failure
            try:
                frame = CV2Utils.resize_image(frame, self.scale_width, self.scale_height)
            except Exception as im_error:
                logger.error(f'Error to resize image : {im_error}')
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
            this should be owned by the first cast which take control
            """

            if CASTMedia.t_todo_event.is_set():
                logger.debug(f"{t_name} We are inside todo :{CASTMedia.cast_name_todo}")
                CASTMedia.t_media_lock.acquire()
                #  take thread name from cast to do list
                for item in CASTMedia.cast_name_todo:
                    name, action, params, added_time = item.split('||')

                    if name not in CASTMedia.cast_names:
                        CASTMedia.cast_name_todo.remove(item)

                    # action is for this thread
                    elif name == t_name:
                        logging.debug(f'To do: {action} for :{t_name}')

                        # use try to capture any failure
                        try:
                            if 'stop' in action:
                                t_todo_stop = True

                            elif 'shot' in action:
                                add_frame = CV2Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                                add_frame = CV2Utils.resize_image(add_frame, self.scale_width, self.scale_height)
                                self.frame_buffer.append(add_frame)
                                if t_multicast:
                                    # resize frame to virtual matrix size
                                    add_frame = CV2Utils.resize_image(frame,
                                                                      self.scale_width * t_cast_x,
                                                                      self.scale_height * t_cast_y)

                                    self.cast_frame_buffer = Utils.split_image_to_matrix(add_frame,
                                                                                         t_cast_x, t_cast_y)
                            elif 'info' in action:
                                t_info = {t_name: {"type": "info", "data": {"start": start_time,
                                                                            "cast_type": 'Media',
                                                                            "tid": threading.current_thread().native_id,
                                                                            "viinput": str(t_viinput),
                                                                            "preview": t_preview,
                                                                            "multicast": t_multicast,
                                                                            "devices": ip_addresses,
                                                                            "fps": 1 / interval,
                                                                            "frames": frame_count,
                                                                            "length": media_length
                                                                            }
                                                   }
                                          }
                                # this wait until queue access is free
                                shared_buffer.put(t_info)
                                logger.debug(f'{t_name} we have put')

                            elif 'close_preview' in action:
                                CV2Utils.cv2_win_close(str(CASTMedia.server_port), 'Media', t_name, t_viinput)
                                t_preview = False

                            elif 'open_preview' in action:
                                t_preview = True

                            elif "reset" in action:
                                CASTMedia.total_frame = 0
                                CASTMedia.total_packet = 0
                                self.reset_total = False

                            elif "host" in action:
                                ip_addresses[0] = params
                                if ddp_host is not None:
                                    ddp_host._destination = params
                                else:
                                    ddp_host = DDPDevice(params)

                            elif "multicast" in action:
                                if t_multicast:
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
                                        elif action_arg == 'pause':
                                            swapper.start_random_replace(delay_arg)
                                        else:
                                            logger.error(f'{t_name} Unknown Multicast action e.g random,1000 : {params}')
                                else:
                                    logger.error(f'{t_name} Not multicast cast')

                        except Exception as error:
                                logger.error(traceback.format_exc())
                                logger.error(f'Action {action} in ERROR from {t_name} : {error}')

                        CASTMedia.cast_name_todo.remove(item)

                if len(CASTMedia.cast_name_todo) == 0:
                    CASTMedia.t_todo_event.clear()
                CASTMedia.t_media_lock.release()

            if t_multicast and (t_cast_y != 1 or t_cast_x != 1):
                """
                    multicast manage any number of devices of same configuration
                    matrix need to be more than 1 x 1
                    each device need to drive the same amount of leds, same config
                    e.g. WLED matrix 16x16 : 3(x) x 2(y)                    
                    ==> this give 6 devices to set into cast_devices list                         
                        (tuple of: device index(0...n) , IP address) 
                        we will manage image of 3x16 leds for x and 2x16 for y    
                        
                    on 10/04/2024: device_number come from list entry order (0...n)
                        
                """

                grid = True

                # resize frame to virtual matrix size
                # frame_art = CV2Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                frame = CV2Utils.resize_image(frame, self.scale_width * t_cast_x, self.scale_height * t_cast_y)

                #
                if frame_count > 1:
                    # split to matrix
                    t_cast_frame_buffer = Utils.split_image_to_matrix(frame, t_cast_x, t_cast_y)
                    # put frame to np buffer (so can be used after by the main)
                    # new cast overwrite, only the last can be seen from GUI
                    if self.put_to_buffer and frame_count <= self.frame_max:
                        add_frame = CV2Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                        add_frame = CV2Utils.resize_image(add_frame, self.scale_width, self.scale_height)
                        self.frame_buffer.append(add_frame)

                else:
                    # populate global cast buffer from first frame only
                    # split to matrix
                    self.cast_frame_buffer = Utils.split_image_to_matrix(frame, t_cast_x, t_cast_y)
                    # validate cast_devices number only once
                    if len(ip_addresses) != len(self.cast_frame_buffer):
                        logger.error(f'{t_name} Cast devices number != sub images number: check cast_devices ')
                        break
                    t_cast_frame_buffer = self.cast_frame_buffer

                # send, keep synchronized
                try:

                    send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                except Exception as error:
                    logger.error(traceback.format_exc())
                    logger.error(f'{t_name} An exception occurred: {error}')
                    break

                # looks like we read an image, go out from the loop...
                if is_image:
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
                    # take only the first entry
                    if t_multicast is False:
                        try:
                            if ip_addresses[0] != '127.0.0.1':
                                # send data to queue
                                ddp_host.send_to_queue(frame_to_send, self.retry_number)
                                CASTMedia.total_packet += ddp_host.frame_count
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

                # put frame to np buffer (so can be used after by the main)
                if self.put_to_buffer and frame_count <= self.frame_max:
                    add_frame = CV2Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                    add_frame = CV2Utils.resize_image(add_frame, self.scale_width, self.scale_height)
                    self.frame_buffer.append(add_frame)

                """
                    stop for non-live video (length not -1)
                    if we reach end of video or request only x frames from index
                """
                if media_length != -1:
                    # only if not image
                    if not is_image:
                        if (frame_count >= media_length or
                                (self.frame_index != 0 and
                                 frame_count >= self.frame_max and
                                 self.put_to_buffer is True)):
                            logger.debug(f"{t_name} Reached END ...")
                            break

            """
            Manage preview window, depend on the platform
            """
            # preview on fixed size window
            if t_preview:

                if str2bool(app_config['preview_proc']):
                    # mandatory for no win platform, cv2.imshow() need to run into Main thread
                    # We use ShareableList to share data between this thread and new process
                    if frame_count == 1:
                        # create a shared list, name is thread name
                        try:
                            sl = ShareableList(
                                [
                                    CASTMedia.total_frame,
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
                                    (1 / interval),
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
                        # create a child process, so cv2.imshow() will run from its own Main Thread
                        sl_process = Process(target=CV2Utils.sl_main_preview, args=(t_name, 'Media',))
                        # start the child process
                        # small delay occur during necessary time OS take to initiate the new process
                        sl_process.start()
                        logger.debug(f'Starting Child Process for Preview : {t_name}')

                    # working with the shared list
                    if frame_count > 1:
                        # what to do from data updated by the child process (mainly user keystroke on preview)
                        if sl[9] is True or sl[18] == '0,0,0':
                            t_todo_stop = True
                        if sl[6] is False:
                            t_preview = False
                        if sl[13] is False:
                            self.text = False
                        else:
                            self.text = True
                        # Update Data on shared List
                        sl[0] = CASTMedia.total_frame
                        # 08/09/2024
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

                    # for win, not necessary to use child process as this work from this thread (avoid overhead)
                    t_preview, t_todo_stop, self.text = CV2Utils.cv2_preview_window(
                        CASTMedia.total_frame,
                        frame,
                        CASTMedia.server_port,
                        t_viinput,
                        t_name,
                        self.preview_top,
                        t_preview,
                        self.preview_w,
                        self.preview_h,
                        t_todo_stop,
                        frame_count,
                        (1 / interval),
                        ip_addresses,
                        self.text,
                        self.custom_text,
                        self.cast_x,
                        self.cast_y,
                        'Media',
                        grid)

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

            """
            do we need to repeat image
            """
            # check repeat for image
            if is_image:
                if t_repeat > 0 or t_repeat < 0:
                    t_repeat -= 1
                    logger.debug(f'{t_name} Remaining repeat : {t_repeat}')
                    frame_count = 0
                    # reset start time to be able to calculate sleep time to reach requested fps
                    start_time = time.time()
                    # Calculate the current time
                    current_time = time.time()
                    auto_expected_time = current_time
                    frame = orig_frame

                else:
                    break

            """
            update data
            """
            frame_count += 1
            CASTMedia.total_frame += 1

        """
            Final : End Media Loop
        """

        CASTMedia.count -= 1
        CASTMedia.cast_names.remove(t_name)
        CASTMedia.t_exit_event.clear()

        self.all_sync = False
        self.cast_sleep = False

        # close preview
        if t_preview is True:
            # if it's an image, we sleep 2 secs before close preview
            if is_image:
                time.sleep(2)

            CV2Utils.cv2_win_close(CASTMedia.server_port, 'Media', t_name, t_viinput)

        # release media
        try:
            if not isinstance(media, np.ndarray):
                media.release()
                logger.debug(f'{t_name} Release Media')
        except Exception as e:
            logger.warning(f'{t_name} Release Media status : {e}')

        # Clean ShareableList
        Utils.sl_clean(sl, sl_process, t_name)

        logger.debug("_" * 50)
        logger.debug(f'Cast {t_name} end using this media: {t_viinput}')
        logger.debug(f'Using these devices: {str(ip_addresses)}')
        logger.debug("_" * 50)

        logger.info(f"{t_name} Cast closed")

    def cast(self, shared_buffer=None, log_ui=None):
        """
            this will run the cast into another thread
            avoid to block the main one
            shared_buffer: if used need to be a queue
            log_ui: used when want to see log msg into main UI
        """
        if log_ui is not None:
            root_logger = logging.getLogger()
            if log_ui not in root_logger:
                logger.addHandler(log_ui)
        thread = threading.Thread(target=self.t_media_cast, args=(shared_buffer,))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        logger.debug('Child Media cast initiated')
