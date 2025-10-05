"""
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
# Data will be sent through 'ddp'  e131 or artnet protocol
# LED datas are sent by using queue feature to avoid any network problem which cause latency
# Once ddp device created, it remains active until application stopped
# A preview can be seen via 'cv2' : pixelart look
#
# in case of camera status() timeout in linux
# camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
# 27/05/2024: cv2.imshow with import av  freeze
#

Overview
This file defines the CASTMedia class, which is responsible for casting media (images, videos, or live capture devices
such as USB cameras) to networked LED devices (e.g., WLED) using protocols like DDP, E1.31, or ArtNet.
The class is designed to be cross-platform and supports advanced features such as multicast (sending to multiple devices),
frame synchronization, real-time preview, and various image processing options.

The file also includes logic for managing multiple concurrent casts, handling network reliability via queues,
and providing a pixel-art style preview using OpenCV. The class is intended to be used as part of a larger system for
synchronizing video or image content with addressable LED hardware.


Key Components
CASTMedia Class
Purpose:
Central class for managing the process of capturing, processing, and transmitting media frames to one or more LED devices
over the network.

Initialization:
Sets up a wide range of configuration options, including network protocol, device addresses, image processing parameters,
preview settings, and synchronization controls.

Threaded Operation:
The main casting logic runs in a separate thread (t_media_cast) to avoid blocking the main application, allowing for
responsive UI and concurrent operations.

Media Input Handling:
Supports various input types: video files, image sequences, live camera feeds, and network streams.
Uses OpenCV for media capture and processing.

Network Protocol Support:

DDP: Uses DDPDevice for direct device communication.
E1.31: Uses E131Device for sACN/E1.31 protocol.
ArtNet: Uses ArtNetDevice for ArtNet protocol. Devices are managed and initialized based on the selected protocol.

Multicast and Matrix Support:
Can split a single image or video frame into a grid and send each section to a different device, enabling large virtual
LED matrices composed of multiple physical devices.

Synchronization:
Supports frame and time synchronization across multiple casts, including auto-sync and manual sync features, to keep
multiple devices in sync with the media source.

Image Processing:
Includes options for resizing, gamma correction, brightness/contrast adjustment, color balancing, flipping, and applying
custom filters.

Preview Functionality:
Provides real-time preview of the output using OpenCV, with support for running the preview in a separate process for
cross-platform compatibility.

Action Executor:
Integrates with an ActionExecutor to handle dynamic actions (e.g., responding to UI events or commands) during casting.

Resource Management:
Handles proper cleanup of resources, including releasing media streams, closing preview windows, and deactivating
network devices.


Supporting Patterns and Utilities
Threading and Concurrency:
Uses Python's threading and concurrent.futures for parallel operations, including multicast sending and action handling.

Shared Memory:
Utilizes multiprocessing.shared_memory.ShareableList for sharing preview frames between processes.

Logging:
Integrates with a custom LoggerManager for detailed debug and error logging.

Configuration Management:
Reads settings from a configuration manager (cfg_mgr) for flexible runtime behavior.

"""
import errno
import os
import threading
import concurrent.futures
import numpy as np
import cv2
import time

from asyncio import run as as_run
from multiprocessing.shared_memory import ShareableList

from src.utl.multicast import IPSwapper
from src.utl.multicast import MultiUtils as Multi
from src.net.ddp_queue import DDPDevice
from src.net.e131_queue import E131Device
from src.net.artnet_queue import ArtNetDevice
from src.utl.text_utils import TextAnimatorMixin

from src.utl.actionutils import *

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.media')
media_logger = logger_manager.logger

Process, Queue = Utils.mp_setup()

"""
Class definition
"""

class CASTMedia(TextAnimatorMixin):
    """Casts media (video, image, or capture device) to DDP devices.

    Sends image data via DDP (e131 or ArtNet) protocol, using a queue for network
    efficiency.  Supports preview, multicast, synchronization, and various image
    processing options.
    """

    count = 0  # initialise running casts count to zero
    total_frame = 0  # total number of processed frames

    cast_names = []  # should contain running Cast instances
    cast_name_todo = []  # list of cast names with action that need to execute from 'to do'
    cast_name_to_sync = []  # list of cast names to sync time

    t_exit_event = threading.Event()  # thread listen event fo exit
    t_todo_event = threading.Event()  # thread listen event for task to do

    t_media_lock = threading.Lock()  # define lock for to do

    total_packet = 0  # net packets number

    def __init__(self):
        self.rate: int = 25
        self.stopcast: bool = True
        self.preview_top: bool = False
        self.preview_w: int = 640
        self.preview_h: int = 360
        self.scale_width: int = 128
        self.scale_height: int = 128
        self.pixel_w = 8
        self.pixel_h = 8
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
        self.preview_text = str2bool(cfg_mgr.app_config['preview_text']) if cfg_mgr.app_config is not None else False
        self.custom_text: str = ""
        self.text_animator = None
        self.overlay_text = str2bool(cfg_mgr.text_config['overlay_text']) if cfg_mgr.app_config is not None else False
        self.anim_text: str = cfg_mgr.text_config['custom_text'] if cfg_mgr.text_config is not None else ""
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
        self.e131_name = 'WVSMedia'  # name for e131/artnet
        self.universe = 1  # universe start number e131/artnet
        self.pixel_count = 0  # number of pixels e131/artnet
        self.packet_priority = 100  # priority for e131
        self.universe_size = 510  # size of each universe e131/artnet
        self.channel_offset = 0  # The channel offset within the universe. e131/artnet
        self.channels_per_pixel = 3  # Channels to use for e131/artnet


    """
    Cast Thread
    """

    def t_media_cast(self, shared_buffer=None, port=0):
        """Cast media to DDP devices in a separate thread.

        This method handles the core logic for capturing, processing, and sending
        media frames to DDP devices. It supports various media types, multicast,
        synchronization, and preview functionalities.
        """
        t_name = threading.current_thread().name
        if CASTMedia.count == 0 or self.reset_total is True:
            CASTMedia.total_frame = 0
            CASTMedia.total_packet = 0

        media_logger.debug(f'Child thread: {t_name}')

        t_send_frame = threading.Event()  # thread listen event to send frame via ddp (for synchro used by multicast)

        t_preview = self.preview
        t_scale_width = self.scale_width
        t_scale_height = self.scale_height
        t_multicast = self.multicast
        t_ddp_multi_names =[]  # all DDP devices for this cast
        t_cast_x = self.cast_x
        t_cast_y = self.cast_y
        t_cast_frame_buffer = []
        t_protocol = self.protocol

        e131_host = None
        ddp_host = None
        artnet_host = None

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

        if not str(self.viinput):
            media_logger.error(f'{t_name} Input media could not be empty')
            return False

        t_viinput = self.viinput

        port = port

        window_name = f"{Utils.get_server_port()}-{t_name}-{str(t_viinput)}"[:64]

        """
        MultiCast inner function protected from what happens outside.
        """

        def send_multicast_image(ip, image):
            """
            This sends an image to an IP address using DDP/e131/artnet, used by multicast
            :param ip:
            :param image:
            :return:
            """
            if t_protocol == 'ddp':
                # timeout provided to not have thread waiting infinitely
                if t_send_frame.wait(timeout=.5):
                    # send ddp data, we select DDPDevice based on the IP
                    for dev in t_ddp_multi_names:
                        if ip == dev._destination:
                            dev.send_to_queue(image, self.retry_number)
                            CASTMedia.total_packet += dev.frame_count
                            break
                else:
                    media_logger.warning(f'{t_name} Multicast frame dropped')

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

        # check IP
        if self.host != '127.0.0.1' and not self.wled:  # 127.0.0.1 should always exist
            if Utils.check_ip_alive(self.host, ping=True):
                media_logger.debug(f'{t_name} We work with this IP {self.host} as first device: number 0')
            else:
                media_logger.error(f'{t_name} Error looks like IP {self.host} do not respond to ping')
                return False

        if t_protocol == 'ddp':
            ddp_host = DDPDevice(self.host)  # init here as queue thread necessary even if 127.0.0.1
            # add to global DDP list
            Utils.update_ddp_list(self.host, ddp_host)

        elif t_protocol =='e131':
            e131_host = E131Device(name=self.e131_name,
                                   ip_address=self.host,
                                   universe=int(self.universe),
                                   pixel_count=int(self.pixel_count),
                                   packet_priority=int(self.packet_priority),
                                   universe_size=int(self.universe_size),
                                   channel_offset=int(self.channel_offset),
                                   channels_per_pixel=int(self.channels_per_pixel),
                                   blackout=True)

            e131_host.activate()

        elif t_protocol =='artnet':
            artnet_host = ArtNetDevice(name=self.e131_name,
                                       ip_address=self.host,
                                       universe=int(self.universe),
                                       pixel_count=int(self.pixel_count),
                                       universe_size=int(self.universe_size),
                                       channel_offset=int(self.channel_offset),
                                       channels_per_pixel=int(self.channels_per_pixel)
                                       )

            artnet_host.activate()


        # retrieve matrix setup from wled and set w/h
        if self.wled:
            status = as_run(Utils.put_wled_live(self.host, on=True, live=True, timeout=1))
            if status is True:
                t_scale_width, t_scale_height = as_run(Utils.get_wled_matrix_dimensions(self.host))
            else:
                media_logger.error(f"{t_name} ERROR to set WLED device {self.host} on 'live' mode")
                return False

        # specifics to Multicast
        swapper = None
        #
        if t_multicast:
            # validate cast_devices list
            if not Multi.is_valid_cast_device(str(self.cast_devices)):
                media_logger.error(f"{t_name} Error Cast device list not compliant to format [(0,'xx.xx.xx.xx')...]")
                return False
            else:
                media_logger.info(f'{t_name} Virtual Matrix size is :' +
                                    str(t_scale_width * t_cast_x) + 'x' + str(t_scale_height * t_cast_y))
                # populate ip_addresses list
                for i in range(len(self.cast_devices)):
                    cast_ip = self.cast_devices[i][1]
                    if self.wled:
                        valid_ip = Utils.check_ip_alive(cast_ip, ping=False)
                    else:
                        valid_ip = Utils.check_ip_alive(cast_ip, ping=True)
                    if valid_ip:
                        if self.wled:
                            status = as_run(Utils.put_wled_live(cast_ip, on=True, live=True, timeout=1))
                            if not status:
                                media_logger.error(f"{t_name} ERROR to set WLED device {self.host} on 'live' mode")
                                return False

                        ip_addresses.append(cast_ip)

                        if t_protocol == 'ddp':
                            # create ddp device for each IP if not exist
                            ddp_exist = False
                            for device in t_ddp_multi_names:
                                if cast_ip == device._destination:
                                    media_logger.warning(f'{t_name} DDPDevice already exist : {cast_ip} as device number {i}')
                                    ddp_exist = True
                                    break
                            if ddp_exist is not True:
                                new_ddp = DDPDevice(cast_ip)
                                t_ddp_multi_names.append(new_ddp)
                                # add to global DDP list
                                Utils.update_ddp_list(cast_ip,new_ddp)
                                media_logger.debug(f'{t_name} DDP Device Created for IP : {cast_ip} as device number {i}')
                    else:
                        media_logger.error(f'{t_name} Not able to validate ip : {cast_ip}')

                # initiate IPSwapper
                swapper = IPSwapper(ip_addresses)

        else:

            ip_addresses=[self.host]

        """
        Second, capture media
        """
        self.pixel_w = t_scale_height
        self.pixel_h = t_scale_height
        self.scale_width = t_scale_width
        self.scale_height = t_scale_height

        frame = None
        orig_frame = None
        is_image = False
        self.frame_buffer = []
        self.cast_frame_buffer = []

        # capture media
        media = cv2.VideoCapture(t_viinput)

        # Check if the capture is successful
        if not media.isOpened():
            media_logger.error(f"{t_name} Error: Unable to open media stream {t_viinput}.")
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
            frame_interval = self.rate
        else:
            media_logger.error(f'{t_name} Rate could not be zero')
            return False

        self.start_text_animator()

        media_logger.info(f"{t_name} Playing media {t_viinput} of length {media_length} at {fps} FPS")
        media_logger.debug(f"{t_name} Stopcast value : {self.stopcast}")

        # detect if we want specific frame index:  not for live video (-1) and image (1)
        if self.frame_index != 0 and media_length > 1:
            media_logger.debug(f"{t_name} Start at frame number {self.frame_index}")
            media.set(cv2.CAP_PROP_POS_FRAMES, self.frame_index - 1)

        # List to keep all running cast objects
        CASTMedia.cast_names.append(t_name)
        CASTMedia.count += 1

        # Calculate the current time
        current_time = time.time()
        auto_expected_time = current_time

        media_logger.debug(f'{t_name} Cast running ...')

        start_time = time.time()

        # --- Initialization (do this once before the loop starts) ---
        action_executor = ActionExecutor(
            class_obj=self,  # Pass the instance of Media/Desktop itself
            port=port,
            t_name=t_name,
            t_viinput=t_viinput,
            t_scale_width=t_scale_width,
            t_scale_height=t_scale_height,
            t_multicast=t_multicast,
            ip_addresses=ip_addresses,  # Pass the list reference
            ddp_host=ddp_host,  # Pass the DDP device instance
            t_cast_x=t_cast_x,
            t_cast_y=t_cast_y,
            start_time=start_time,
            initial_preview_state=t_preview,  # Pass the initial preview state
            interval=interval,
            media_length=media_length,
            swapper=swapper,
            shared_buffer=shared_buffer,  # queue
            logger=media_logger,
            t_protocol=t_protocol
        )
        # --- End Initialization ---

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
                    if self.auto_sync is True and current_time - auto_expected_time >= self.auto_sync_delay:
                        time_to_set = self.sync_to_time
                        self.cast_sync = True
                        media_logger.debug(f"{t_name}  Name to sync  :{CASTMedia.cast_name_to_sync}")
                    
                        CASTMedia.t_media_lock.acquire()
                        if self.all_sync is True and len(CASTMedia.cast_name_to_sync) == 0:
                            # populate cast names to sync
                            CASTMedia.cast_name_to_sync = CASTMedia.cast_names.copy()
                            # add additional time, can help if cast number > 0 to try to avoid small decay
                            time_to_set += self.add_all_sync_delay
                            media_logger.debug(f"{t_name}  Got these to sync from auto :{CASTMedia.cast_name_to_sync}")
                        CASTMedia.t_media_lock.release()
                    
                        auto_expected_time = current_time
                        media_logger.debug(f'{t_name} Auto Sync Cast to time :{time_to_set}')

                    if self.all_sync is True and self.cast_sync is True:

                        CASTMedia.t_media_lock.acquire()

                        # populate cast names to sync if necessary
                        if len(CASTMedia.cast_name_to_sync) == 0 and self.auto_sync is False:
                            CASTMedia.cast_name_to_sync = CASTMedia.cast_names.copy()
                            media_logger.debug(f"{t_name}  Got these to sync  :{CASTMedia.cast_name_to_sync}")

                        # take only cast not already synced
                        if t_name in CASTMedia.cast_name_to_sync:
                            self.cast_sleep = True
                            # remove thread name from cast to sync list
                            media_logger.debug(f"{t_name} remove from all sync")
                            CASTMedia.cast_name_to_sync.remove(t_name)
                            # sync cast
                            media.set(cv2.CAP_PROP_POS_MSEC, self.sync_to_time)
                            media_logger.debug(f'{t_name} ALL Sync Cast to time :{self.sync_to_time}')

                            media_logger.debug(f'{t_name} synced')

                            # if no more, reset all_sync
                            if len(CASTMedia.cast_name_to_sync) == 0:
                                if self.auto_sync is False:
                                    self.all_sync = False
                                self.cast_sync = False
                                self.cast_sleep = False
                                media_logger.debug(f"{t_name} All sync finished")

                        CASTMedia.t_media_lock.release()

                        media_logger.debug(f'{t_name} go to sleep if necessary')
                        while (self.cast_sleep is True and
                               self.cast_sync is True and
                               len(CASTMedia.cast_name_to_sync) > 0):
                            # sleep until all remaining casts sync
                            time.sleep(.001)
                        media_logger.debug(f'{t_name} exit sleep')

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
                                media_logger.debug(f'{t_name} Sync Cast to time :{self.sync_to_time}')
                #
                # read frame for all
                #
                success, frame = media.read()
                if not success:
                    if frame_count != media_length:
                        media_logger.warning(f'{t_name} Not all frames have been read')
                        break

                    else:
                        media_logger.debug(f'{t_name} Media reached END')
                        # manage the repeat feature, if -1 then unlimited
                        if t_repeat > 0 or t_repeat < 0:
                            t_repeat -= 1
                            media_logger.debug(f'{t_name} Remaining repeat : {t_repeat}')
                            # reset media to start
                            media.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            # read one frame
                            success, frame = media.read()
                            if not success:
                                media_logger.error(f'{t_name} Not able to repeat')
                                break
                            frame_count = 0
                            # reset start time to be able to calculate sleep time to reach requested fps
                            start_time = time.time()
                            # Calculate the current time
                            current_time = time.time()
                            auto_expected_time = current_time

                        else:
                            break

            # resize to requested size
            # this will validate media passed to cv2
            # common part for image media_length = 1 or live video = -1 or video > 1
            # break in case of failure
            try:
                frame = CV2Utils.resize_image(frame, t_scale_width, t_scale_height)
            except Exception as im_error:
                media_logger.error(f'Error to resize image : {im_error}')
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

                frame = ImageUtils.process_filters_image(frame, filters=filters)

            # flip vertical/horizontal: 0,1
            if self.flip:
                frame = cv2.flip(frame, self.flip_vh)

            # Superimpose animated text if enabled
            if self.text_animator:
                text_overlay_bgra = self.text_animator.generate()
                if text_overlay_bgra is not None:
                    # Ensure frame is BGR before overlaying
                    if len(frame.shape) == 2:
                        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                    elif frame.shape[2] == 4:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    
                    frame = CV2Utils.overlay_bgra_on_bgr(frame, text_overlay_bgra)

            # put frame to np buffer (so can be used after by the main)
            if self.put_to_buffer and frame_count <= self.frame_max:
                add_frame = CV2Utils.pixelart_image(frame, t_scale_width, t_scale_height)
                add_frame = CV2Utils.resize_image(add_frame, t_scale_width, t_scale_height)

                self.frame_buffer.append(add_frame)

            """
            check if something to do
            manage concurrent access to the list by using lock feature
            event clear only when no more item in list
            this should be owned by the first cast which take control
            """
            if CASTMedia.t_todo_event.is_set() and shared_buffer is not None:
                # only one running cast at time will take care of that
                CASTMedia.t_media_lock.acquire()
                media_logger.debug(f"{t_name} We are inside todo :{CASTMedia.cast_name_todo}")
                # will read cast_name_todo list and see if something to do
                t_todo_stop, t_preview, add_frame_buffer, add_cast_frame_buffer = action_executor.process_actions(frame,
                                                                                                              frame_count)
                if add_frame_buffer is not None:
                    self.frame_buffer.append(add_frame_buffer)
                if add_cast_frame_buffer is not None:
                    self.cast_frame_buffer.append(add_cast_frame_buffer)

                # if list is empty, no more for any cast
                if len(CASTMedia.cast_name_todo) == 0:
                    CASTMedia.t_todo_event.clear()
                # release once task finished for this cast
                CASTMedia.t_media_lock.release()

            """
            End To do
            """

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
                # frame_art = CV2Utils.pixelart_image(frame, t_scale_width, t_scale_height)
                frame = CV2Utils.resize_image(frame, t_scale_width * t_cast_x, t_scale_height * t_cast_y)

                #
                if frame_count > 1:
                    # split to matrix
                    t_cast_frame_buffer = Multi.split_image_to_matrix(frame, t_cast_x, t_cast_y)
                    # put frame to np buffer (so can be used after by the main)
                    # a new cast overwrite buffer, only the last cast buffer can be seen on GUI
                    if self.put_to_buffer and frame_count <= self.frame_max:
                        add_frame = CV2Utils.pixelart_image(frame, t_scale_width, t_scale_height)
                        add_frame = CV2Utils.resize_image(add_frame, t_scale_width, t_scale_height)
                        self.frame_buffer.append(add_frame)

                else:
                    # populate global cast buffer from first frame only
                    # split to matrix
                    self.cast_frame_buffer = Multi.split_image_to_matrix(frame, t_cast_x, t_cast_y)
                    # validate cast_devices number only once
                    if len(ip_addresses) != len(self.cast_frame_buffer):
                        media_logger.error(f'{t_name} Cast devices number != sub images number: check cast_devices ')
                        break
                    t_cast_frame_buffer = self.cast_frame_buffer

                # send, keep synchronized
                try:

                    send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                except Exception as error:
                    media_logger.error(traceback.format_exc())
                    media_logger.error(f'{t_name} An exception occurred: {error}')
                    break

                # if we read an image, go out from the loop...
                if is_image:
                    break

            else:

                grid = False

                # resize frame for sending to device
                frame_to_send = CV2Utils.resize_image(frame, t_scale_width, t_scale_height)
                # resize frame to pixelart
                frame = CV2Utils.pixelart_image(frame, t_scale_width, t_scale_height)

                # Protocols run in separate thread to avoid block main loop
                # here we feed the queue that is read by Net thread
                if t_protocol == "ddp":
                    # take only the first entry
                    if t_multicast is False:
                        try:
                            if ip_addresses[0] != '127.0.0.1':
                                # send data to queue
                                ddp_host.send_to_queue(frame_to_send, self.retry_number)
                                CASTMedia.total_packet += ddp_host.frame_count
                        except Exception as tr_error:
                            media_logger.error(traceback.format_exc())
                            media_logger.error(f"{t_name} Exception Error on IP device : {tr_error}")
                            break

                    # if multicast and more than one ip address and matrix size 1 * 1
                    # we send the frame to all cast devices
                    elif t_multicast is True and t_cast_x == 1 and t_cast_y == 1 and len(ip_addresses) > 1:

                        t_cast_frame_buffer = [frame_to_send]

                        # send, keep synchronized
                        try:

                            send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                        except Exception as error:
                            media_logger.error(traceback.format_exc())
                            media_logger.error(f'{t_name} An exception occurred: {error}')
                            break
                    # if multicast and only one IP
                    else:
                        media_logger.error(f'{t_name} Not enough IP devices defined. Modify Multicast param')
                        break

                elif t_protocol == 'e131':

                    e131_host.send_to_queue(frame_to_send)

                elif t_protocol == 'artnet':

                    artnet_host.send_to_queue(frame_to_send)

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
                            media_logger.debug(f"{t_name} Reached END ...")
                            break

            """
            Manage preview window, depend on the platform
            """
            # preview on fixed size window
            if t_preview:

                if str2bool(cfg_mgr.app_config['preview_proc']):
                    # mandatory for no win platform, cv2.imshow() need to run into Main thread
                    # We use ShareableList to share data between this thread and new process
                    #
                    if frame_count == 1:
                        media_logger.debug(f'{t_name} First frame detected for SL')
                        # Create a (9999, 9999, 3) array with all values set to 111 to reserve memory
                        frame_info = frame.shape
                        frame_info_list = list(frame_info)
                        frame_info = tuple(frame_info_list)
                        full_array = np.full(frame_info, 111, dtype=np.uint8)
                        # create a shared list, name is thread name + _p
                        sl_name = f'{t_name}_p'
                        try:
                            sl = ShareableList(
                                [
                                    CASTMedia.total_frame,
                                    full_array.tobytes(),
                                    port,
                                    t_viinput,
                                    t_name,
                                    self.preview_top,
                                    t_preview,
                                    self.preview_w,
                                    self.preview_h,
                                    self.pixel_w,
                                    self.pixel_h,
                                    t_todo_stop,
                                    frame_count,
                                    frame_interval,
                                    str(ip_addresses),
                                    self.preview_text,
                                    self.custom_text,
                                    self.cast_x,
                                    self.cast_y,
                                    grid,
                                    str(list(frame_info))
                                ],
                                name=sl_name
                            )
                            media_logger.debug(f'{t_name} SL created ')

                        except OSError as e:
                            if e.errno == errno.EEXIST:  # errno.EEXIST is 17 (File exists)
                                media_logger.warning(f"Shared memory '{sl_name}' already exists. Attaching to it.")
                                sl = ShareableList(name=sl_name)

                        except Exception as e:
                            media_logger.error(traceback.format_exc())
                            media_logger.error(f'{t_name} Exception on shared list creation : {e}')
                            break

                        # run main_preview in another process
                        # create a child process, so cv2.imshow() will run from its own Main Thread
                        media_logger.debug(f'Define sl_process for Preview : {sl_name}')
                        window_name = f"{Utils.get_server_port()}-{t_name}-{str(t_viinput)}"[:64]
                        sl_process = Process(target=CV2Utils.sl_main_preview, args=(sl_name, 'Media', window_name,))
                        # start the child process
                        # small delay occur during necessary time OS take to initiate the new process
                        media_logger.debug(f'Starting Child Process for Preview : {sl_name}')
                        sl_process.start()
                        media_logger.debug(f'Child Process started for Preview : {sl_name}')

                    # working with the shared list
                    if frame_count > 1:
                        try:
                            # what to do from data updated by the child process (mainly user keystroke on preview)
                            if sl[11] is True:
                                t_todo_stop = True
                            if sl[6] is False:
                                t_preview = False
                            self.preview_text = sl[15] is not False
                            # Update Data on shared List
                            sl[0] = CASTMedia.total_frame
                            #
                            # append not zero value to bytes to solve ShareableList bug
                            # see https://github.com/python/cpython/issues/106939
                            sl[1] = CV2Utils.frame_add_one(frame)
                            #
                            sl[5] = self.preview_top
                            sl[7] = self.preview_w
                            sl[8] = self.preview_h
                            sl[9] = self.pixel_w
                            sl[10] = self.pixel_h
                            sl[12] = frame_count
                            sl[15] = self.preview_text

                        except Exception as e:
                            media_logger.error(traceback.format_exc())
                            media_logger.error(f'Error to set ShareableList : {e}')
                            t_preview = False

                else:

                    # for win, not necessary to use child process as this work from this thread (avoid overhead)
                    if not CV2Utils.window_exists(window_name):
                        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

                    t_preview, t_todo_stop, self.preview_text = CV2Utils.cv2_display_frame(
                        CASTMedia.total_frame,
                        frame,
                        port,
                        t_viinput,
                        t_name,
                        self.preview_top,
                        t_preview,
                        self.preview_w,
                        self.preview_h,
                        self.pixel_w,
                        self.pixel_h,
                        t_todo_stop,
                        frame_count,
                        frame_interval,
                        ip_addresses,
                        self.preview_text,
                        self.custom_text,
                        self.cast_x,
                        self.cast_y,
                        grid)

            """
            do we need to sleep to be compliant with selected rate (fps)
            """
            if not CASTMedia.t_todo_event.is_set():
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
                    media_logger.debug(f'{t_name} Remaining repeat : {t_repeat}')
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

            CV2Utils.cv2_win_close(port, 'Media', t_name, t_viinput)

        # release media
        try:
            if not isinstance(media, np.ndarray):
                media.release()
                media_logger.debug(f'{t_name} Release Media')
        except Exception as e:
            media_logger.warning(f'{t_name} Release Media status : {e}')

        # Clean ShareableList
        Utils.sl_clean(sl, sl_process, t_name)

        # stop e131/artnet
        if t_protocol == 'e131':
            e131_host.deactivate()
        elif t_protocol == 'artnet':
            artnet_host.deactivate()

        media_logger.debug("_" * 50)
        media_logger.debug(f'Cast {t_name} end using this media: {t_viinput}')
        media_logger.debug(f'Using these devices: {ip_addresses}')
        media_logger.debug("_" * 50)

        media_logger.info(f"{t_name} Cast closed")

    def cast(self, shared_buffer=None, log_ui=None):
        """
            this will run the cast into another thread
            avoid to block the main one
            shared_buffer: if used need to be a queue
            log_ui: used when want to see log msg into main UI
        """
        if log_ui is not None:
            root_logger = media_logger.getLogger()
            if log_ui not in root_logger:
                media_logger.addHandler(log_ui)
        if os.getenv('WLEDVideoSync_trace'):
            threading.settrace(self.t_media_cast())
        thread = threading.Thread(target=self.t_media_cast, args=(shared_buffer,Utils.get_server_port(),))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        media_logger.debug('Child Media cast initiated')
        return thread

# example: this work on windows with camera set as device 0
if __name__ == "__main__":

    test = CASTMedia()
    test.stopcast = False
    test.viinput=0
    test.preview=True
    test.cast()
    while True:
        time.sleep(40)
        break
    test.stopcast=True
    print('end')