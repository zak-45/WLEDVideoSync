"""
 a: zak-45
 d: 13/03/2024
 v: 1.0.0

 CASTDesktop class

           Cast your screen or frame (np) from sl-queue to Artnet/e131/ddp device (e.g.WLED)
                               or others

 logger.info(av.codec.codecs_available)
 pyav --codecs

# This Python file (desktop.py) implements the CASTDesktop class, which allows users to cast their desktop screen,
# a specific window, or a selected area to various devices supporting Art-Net, E1.31, or DDP (e.g., WLED).
# It leverages the PyAV library for video capture and encoding, eliminating the need for a separate FFmpeg installation.
# The class supports casting to a single device or multiple devices in a multicast setup, enabling synchronized display
# across a virtual matrix of devices. It also includes options for video recording, real-time preview, and image
# adjustments like brightness, contrast, gamma, and saturation.
#
# windows : ffmpeg -f gdigrab -framerate 30 -video_size 640x480 -show_region 1 -i desktop output.mkv
# linux   : ffmpeg -video_size 1024x768 -framerate 25 -f x11grab -i :0.0+100,200 output.mp4
# darwin  : ffmpeg -f avfoundation -i "<screen device index>:<audio device index>" output.mkv
(ffmpeg -hide_banner -list_devices true -f avfoundation -i dummy)
#
# By using PyAV, ffmpeg do not need to be installed on the OS.
# PyAV is a Pythonic binding for ffmpeg.
# This utility aim to be cross-platform.
# You can cast your entire desktop screen or only window content or desktop area.
# Data will be sent through 'ddp' /artnet / e131 protocol or stream via udp:// rtp:// etc ...
# Net data are sent by using queue feature to avoid any network problem which cause latency

 27/05/2024: cv2.imshow with import av  freeze on not win OS
 to fix it, cv2.imshow can run from its own process with cost of additional overhead: set preview_proc = True

"""
import errno
import ast
import sys
import os
import time
# import imageio.v3 as iio
import concurrent.futures
import threading
import cv2
import traceback
import numpy as np

from src.utl import actionutils

from multiprocessing.shared_memory import ShareableList
from str2bool import str2bool
from asyncio import run as as_run
from src.net.ddp_queue import DDPDevice
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils, ImageUtils
from src.utl.multicast import IPSwapper
from src.utl.multicast import MultiUtils as Multi
from src.net.e131_queue import E131Queue
from src.net.artnet_queue import ArtNetQueue
from configmanager import ConfigManager

from src.utl.sharedlistclient import SharedListClient
from src.utl.sharedlistmanager import SharedListManager

Process, Queue = Utils.mp_setup()

cfg_mgr = ConfigManager(logger_name='WLEDLogger.desktop')

"""
When this env var exist, this mean run from the one-file executable.
Load of the config is not possible, folder config should not exist.
This avoid FileNotFoundError.
This env not exist when run the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    """
    Retrieve  config keys
    """
    if cfg_mgr.app_config is not None:
        cfg_text = str2bool(cfg_mgr.app_config['text']) is True


"""
Class definition
"""
class ExitFromLoop(Exception):
    """ Raise when need to exit from loop """
    pass

class CASTDesktop:
    """Casts desktop screen or window content to DDP devices.

    Captures screen or window content using PyAV, processes the frames, and sends
    them to DDP devices (e.g., WLED) via Art-Net, E1.31, or DDP protocols. Supports
    multicast, preview, recording, and image adjustments.
    """

    count = 0  # initialise running casts count to zero
    total_frame = 0  # total number of processed frames

    cast_names = []  # list of running threads
    cast_name_todo = []  # list of cast names that need to execute to do

    t_exit_event = threading.Event()  # thread listen event

    t_todo_event = threading.Event()  # thread listen event for task to do
    t_desktop_lock = threading.Lock()  # define lock for to do

    total_packet = 0  # net packets number

    def __init__(self):
        self.rate: int = 25
        self.stopcast: bool = True
        self.scale_width: int = 128
        self.scale_height: int = 128
        self.pixel_w = 8
        self.pixel_h = 8
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
        self.text = str2bool(cfg_mgr.app_config['text']) if cfg_mgr.app_config is not None else False
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
        self.monitor_number: int = 0  # monitor to use for area selection / mss
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
            self.viinput = '"0:0"'
            self.viformat: str = 'avfoundation'

        else:
            self.viinput = ''
            self.viformat = ''

        self.vi_codec: str = 'libx264rgb'
        self.windows_titles = {}

        self.e131_name = 'WVSDesktop'  # name for e131/artnet
        self.universe = 1  # universe start number e131/artnet
        self.pixel_count = 0  # number of pixels e131/artnet
        self.packet_priority = 100  # priority for e131
        self.universe_size = 510  # size of each universe e131/artnet
        self.channel_offset = 0  # The channel offset within the universe. e131/artnet
        self.channels_per_pixel = 3  # Channels to use for e131/artnet

    def t_desktop_cast(self, shared_buffer=None, port=0):
        """
            Cast desktop screen or a window content based on the title
        """

        t_name = threading.current_thread().name
        if CASTDesktop.count == 0 or self.reset_total is True:
            CASTDesktop.total_frame = 0
            CASTDesktop.total_packet = 0

        cfg_mgr.logger.debug(f'Child thread: {t_name}')

        t_send_frame = threading.Event()  # thread listen event to send frame via ddp, for multicast synchro

        t_preview = self.preview
        t_scale_width = self.scale_width
        t_scale_height = self.scale_height
        t_multicast = self.multicast
        t_ddp_multi_names =[]
        t_cast_x = self.cast_x
        t_cast_y = self.cast_y
        media_length = -1
        frame_count = 0

        frame = None
        sl_queue = None

        sl = None
        sl_process = None
        sl_client = None
        sl_manager = None
        sl_name_q = f'{t_name}_q'

        t_todo_stop = False

        t_protocol = self.protocol
        e131_host = None
        ddp_host = None
        artnet_host = None

        port = port

        if cfg_mgr.desktop_config is not None:
            if cfg_mgr.desktop_config['capture'] != '':
                capture_methode = cfg_mgr.desktop_config['capture']
            else:
                capture_methode = 'av'
        else:
            capture_methode = 'av'

        if capture_methode == 'av':
            import av
        elif capture_methode == 'mss':
            import mss

        """
        Cast devices
        """
        ip_addresses = []

        """
        av 
        """

        input_container = None
        output_container = False
        output_stream = None

        """
        mss
        """
        mss_window_name = ''
        monitor = self.monitor_number
        """
        """
        # Calculate the interval between frames in seconds (fps)
        if self.rate != 0:
            interval: float = 1.0 / self.rate
        else:
            cfg_mgr.logger.error(f'{t_name} Rate could not be zero')
            return False

        """
        MultiCast inner function protected from what happens outside.
        """

        def send_multicast_image(ip, image):
            """
            This sends an image to an IP address
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
                            CASTDesktop.total_packet += dev.frame_count
                            break
                else:
                    cfg_mgr.logger.warning(f'{t_name} Multicast frame dropped')

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
        actions processing
        """
        def do_action(iframe, i_preview, i_todo_stop):
            """
            check if something to do
            manage concurrent access to the list by using lock feature
            event clear only when no more item in list
            """

            # only one running cast at time will take care of that
            CASTDesktop.t_desktop_lock.acquire()
            cfg_mgr.logger.debug(f"{t_name} We are inside todo :{CASTDesktop.cast_name_todo}")
            # will read cast_name_todo list and see if something to do
            i_todo_stop, i_preview = actionutils.execute_actions(CASTDesktop,
                                                                 iframe,
                                                                 t_name,
                                                                 t_viinput,
                                                                 t_scale_width,
                                                                 t_scale_height,
                                                                 t_multicast,
                                                                 ip_addresses,
                                                                 ddp_host,
                                                                 t_cast_x,
                                                                 t_cast_y,
                                                                 start_time,
                                                                 i_todo_stop,
                                                                 i_preview,
                                                                 frame_interval,
                                                                 frame_count,
                                                                 media_length,
                                                                 swapper,
                                                                 shared_buffer,
                                                                 self.frame_buffer,
                                                                 self.cast_frame_buffer,
                                                                 cfg_mgr.logger,
                                                                 t_protocol)
            # if list is empty, no more for any cast
            if len(CASTDesktop.cast_name_todo) == 0:
                CASTDesktop.t_todo_event.clear()
            # release once task finished for this cast
            CASTDesktop.t_desktop_lock.release()

            return i_preview, i_todo_stop

        """
        end actions
        """

        """
        frame processing
        """
        def process_frame(iframe):

            # resize frame for sending to device
            iframe = CV2Utils.resize_image(iframe, t_scale_width, t_scale_height)

            # adjust gamma
            iframe = cv2.LUT(iframe, ImageUtils.gamma_correct_frame(self.gamma))
            # auto brightness contrast
            if self.auto_bright:
                iframe = ImageUtils.automatic_brightness_and_contrast(iframe, self.clip_hist_percent)
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

                iframe = ImageUtils.process_filters_image(iframe, filters=filters)

            # flip vertical/horizontal: 0,1
            if self.flip:
                iframe = cv2.flip(iframe, self.flip_vh)

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

                i_grid = True

                # resize frame to virtual matrix size
                # frame_art = CV2Utils.pixelart_image(iframe, t_scale_width, t_scale_height)
                iframe = CV2Utils.resize_image(iframe,
                                              t_scale_width * t_cast_x,
                                              t_scale_height * t_cast_y)

                if frame_count > 1:
                    # split to matrix
                    t_cast_frame_buffer = Multi.split_image_to_matrix(iframe, t_cast_x, t_cast_y)
                    # save frame to np buffer if requested (so can be used after by the main)
                    if self.put_to_buffer and frame_count <= self.frame_max:
                        self.frame_buffer.append(iframe)

                else:
                    # split to matrix
                    self.cast_frame_buffer = Multi.split_image_to_matrix(iframe, t_cast_x, t_cast_y)

                    # validate cast_devices number
                    if len(ip_addresses) != len(self.cast_frame_buffer):
                        cfg_mgr.logger.error(
                            f'{t_name} Cast devices number != sub images number: check cast_devices ')
                        raise ExitFromLoop

                    t_cast_frame_buffer = self.cast_frame_buffer

                # send, keep synchronized
                try:

                    send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                except Exception as er:
                    cfg_mgr.logger.error(traceback.format_exc())
                    cfg_mgr.logger.error(f'{t_name} An exception occurred: {er}')
                    raise ExitFromLoop


            else:

                i_grid = False

                frame_to_send = iframe
                # resize frame to pixelart
                iframe = CV2Utils.pixelart_image(iframe, t_scale_width, t_scale_height)

                # Protocols run in separate thread to avoid block main loop
                # here we feed the queue that is read by Net thread
                if t_protocol == "ddp":
                    # take only the first IP from list
                    if t_multicast is False:
                        try:
                            if ip_addresses[0] != '127.0.0.1':
                                # send data to queue
                                ddp_host.send_to_queue(frame_to_send, self.retry_number)
                                CASTDesktop.total_packet += ddp_host.frame_count
                        except Exception as tr_error:
                            cfg_mgr.logger.error(traceback.format_exc())
                            cfg_mgr.logger.error(f"{t_name} Exception Error on IP device : {tr_error}")
                            raise ExitFromLoop

                    # if multicast and more than one ip address and matrix size 1 * 1
                    # we send the frame to all cast devices
                    elif t_multicast is True and t_cast_x == 1 and t_cast_y == 1 and len(ip_addresses) > 1:

                        t_cast_frame_buffer = [frame_to_send]

                        # send, keep synchronized
                        try:

                            send_multicast_images_to_ips(t_cast_frame_buffer, ip_addresses)

                        except Exception as er:
                            cfg_mgr.logger.error(traceback.format_exc())
                            cfg_mgr.logger.error(f'{t_name} An exception occurred: {er}')
                            raise ExitFromLoop

                    # if multicast and only one IP
                    else:
                        cfg_mgr.logger.error(f'{t_name} Not enough IP devices defined. Modify Multicast param')
                        raise ExitFromLoop

                elif t_protocol == 'e131':

                    e131_host.send_to_queue(frame_to_send)

                elif t_protocol == 'artnet':

                    artnet_host.send_to_queue(frame_to_send)

                # save frame to np buffer if requested (so can be used after by the main)
                if self.put_to_buffer and frame_count <= self.frame_max:
                    self.frame_buffer.append(frame)

            """
            Record
            """
            if self.record and out_file is not None:
                out_file.write_frame(frame)


            return iframe, i_grid

        """
        end frame process
        """

        """
        preview process
        Manage preview window, depend on the platform
        """
        def show_preview(iframe, i_preview, i_todo_stop, i_grid):
            # preview on fixed size window

            if str2bool(cfg_mgr.app_config['preview_proc']):
                # for non-win platform mainly, cv2.imshow() need to run into Main thread
                # We use ShareableList to share data between this thread and new process
                # preview window is managed by CV2Utils.sl_main_preview() running from sl_process

                # working with the shared list
                # what to do from data updated by the child process (keystroke from preview window)
                if sl[11] is True:
                    i_todo_stop = True
                elif sl[6] is False:
                    i_preview = False
                else:
                    # Update Data on shared List
                    self.text = sl[15] is not False
                    sl[0] = CASTDesktop.total_frame
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
                    sl[15] = self.text

            else:

                # for win, not necessary to use child process as this work from thread (avoid overhead)
                if not CV2Utils.window_exists(win_name):
                    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

                i_preview, i_todo_stop, self.text = CV2Utils.cv2_preview_window(
                    CASTDesktop.total_frame,
                    iframe,
                    port,
                    t_viinput,
                    t_name,
                    self.preview_top,
                    i_preview,
                    self.preview_w,
                    self.preview_h,
                    self.pixel_w,
                    self.pixel_h,
                    i_todo_stop,
                    frame_count,
                    frame_interval,
                    ip_addresses,
                    self.text,
                    self.custom_text,
                    self.cast_x,
                    self.cast_y,
                    i_grid)

            return i_preview, i_todo_stop

        """
        end preview process
        """

        """
        create shareable list        
        """
        def create_preview_sl(i_frame, i_grid):
            i_sl = None
            # Create a (9999, 9999, 3) array with all values set to 255 to reserve memory
            frame_info = i_frame.shape
            frame_info_list = list(frame_info)
            frame_info = tuple(frame_info_list)
            full_array = np.full(frame_info, 255, dtype=np.uint8)
            # create a shared list, name is thread name + _p
            sl_name_p = f'{t_name}_p'
            try:
                i_sl = ShareableList(
                    [
                        CASTDesktop.total_frame,
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
                        self.text,
                        self.custom_text,
                        self.cast_x,
                        self.cast_y,
                        i_grid,
                        str(list(frame_info))
                    ],
                    name=sl_name_p)

            except OSError as er:
                if er.errno == errno.EEXIST:  # errno.EEXIST is 17 (File exists)
                    cfg_mgr.logger.warning(f"Shared memory '{sl_name_p}' already exists. Attaching to it.")
                    i_sl = ShareableList(name=sl_name_p)

            except Exception as er:
                cfg_mgr.logger.error(traceback.format_exc())
                cfg_mgr.logger.error(f'{t_name} Exception on shared list {sl_name_p} creation : {er}')

            # run main_preview in another process
            # create a child process, so cv2.imshow() will run from its Main Thread
            w_name = f"{Utils.get_server_port()}-{t_name}-{str(t_viinput)}"
            i_sl_process = Process(target=CV2Utils.sl_main_preview, args=(sl_name_p, 'Desktop', w_name,))
            i_sl_process.daemon = True
            # start the child process
            # small delay should occur, OS take some time to initiate the new process
            i_sl_process.start()
            cfg_mgr.logger.debug(f'Starting Child Process for Preview : {sl_name_p}')

            return i_sl, i_sl_process

        def need_to_sleep():
            """
            do we need to sleep to be compliant with selected rate (fps)
            """
            # Calculate the current time
            current_time = time.time()

            # Calculate the time to sleep to maintain the desired FPS
            sleep_time = expected_time - current_time

            if sleep_time > 0:
                time.sleep(sleep_time)

        """
        First, check devices 
        """

        # check IP
        if self.host != '127.0.0.1' and not self.wled:  # 127.0.0.1 should always exist
            if Utils.check_ip_alive(self.host, ping=True):
                cfg_mgr.logger.debug(f'{t_name} We work with this IP {self.host} as first device: number 0')
            else:
                cfg_mgr.logger.error(f'{t_name} Error looks like IP {self.host} do not respond to ping')
                return

        if t_protocol == 'ddp':
            ddp_host = DDPDevice(self.host)  # init here as queue thread necessary even if 127.0.0.1
            # add to global DDP list
            Utils.update_ddp_list(self.host, ddp_host)

        elif t_protocol == 'e131':
            e131_host = E131Queue(name=self.e131_name,
                                  ip_address=self.host,
                                  universe=int(self.universe),
                                  pixel_count=int(self.pixel_count),
                                  packet_priority=int(self.packet_priority),
                                  universe_size=int(self.universe_size),
                                  channel_offset=int(self.channel_offset),
                                  channels_per_pixel=int(self.channels_per_pixel),
                                  blackout=True)

            e131_host.activate()

        elif t_protocol == 'artnet':
            artnet_host = ArtNetQueue(name=self.e131_name,
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
            if status:
                t_scale_width, t_scale_height = as_run(Utils.get_wled_matrix_dimensions(self.host))
            else:
                cfg_mgr.logger.error(f"{t_name} ERROR to set WLED device {self.host} on 'live' mode")
                return

        swapper = None

        # specifics for Multicast
        if t_multicast:
            # validate cast_devices list
            if not Multi.is_valid_cast_device(str(self.cast_devices)):
                cfg_mgr.logger.error(f"{t_name} Error Cast device list not compliant to format [(0,'xx.xx.xx.xx')...]")
                return
            else:
                cfg_mgr.logger.info(f'{t_name} Virtual Matrix size is : \
                            {str(t_scale_width * t_cast_x)}x{str(t_scale_height * t_cast_y)}')
                # populate ip_addresses list
                for i in range(len(self.cast_devices)):
                    cast_ip = self.cast_devices[i][1]
                    valid_ip = Utils.check_ip_alive(cast_ip, ping=True)
                    if valid_ip:
                        if self.wled:
                            status = as_run(Utils.put_wled_live(cast_ip, on=True, live=True, timeout=1))
                            if not status:
                                cfg_mgr.logger.error(f"{t_name} ERROR to set WLED device {self.host} on 'live' mode")
                                return

                        ip_addresses.append(cast_ip)

                        if t_protocol == 'ddp':
                            # create ddp device for each IP if not exist
                            ddp_exist = False
                            for device in t_ddp_multi_names:
                                if cast_ip == device._destination:
                                    cfg_mgr.logger.warning(f'{t_name} DDPDevice already exist : {cast_ip} as device number {i}')
                                    ddp_exist = True
                                    break
                            if ddp_exist is not True:
                                new_ddp = DDPDevice(cast_ip)
                                t_ddp_multi_names.append(new_ddp)
                                # add to global DDP list
                                Utils.update_ddp_list(cast_ip,new_ddp)
                                cfg_mgr.logger.debug(f'{t_name} DDP Device Created for IP : {cast_ip} as device number {i}')
                    else:
                        cfg_mgr.logger.error(f'{t_name} Not able to validate ip : {cast_ip}')

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

        self.frame_buffer = []
        self.cast_frame_buffer = []
        frame_interval = self.rate

        if self.viinput == 'queue':

            if cfg_mgr.manager_config is not None:
                sl_manager = SharedListManager(cfg_mgr.manager_config['manager_ip'],
                                               int(cfg_mgr.manager_config['manager_port']))
                sl_client = SharedListClient(cfg_mgr.manager_config['manager_ip'],
                                             int(cfg_mgr.manager_config['manager_port']))
            else:
                sl_manager = SharedListManager()
                sl_client = SharedListClient()

            # check server is running
            result = sl_client.connect()
            if not result:
                sl_manager.start()
                sl_client.connect()

            # create ShareAbleList
            sl_queue = sl_client.create_shared_list(sl_name_q, t_scale_width, t_scale_height, time.time())

        elif capture_methode == 'av':

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
                    self.viinput = f'title={self.viinput[4:]}'
                elif sys.platform.lower() == 'linux':
                    try:
                        # list all id for a title name (should be only one ...)
                        window_ids = []
                        # Iterate through each process
                        for process_name, process_details in self.windows_titles.items():
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
                            cfg_mgr.logger.warning(f'More than one hWnd (ID) returned, you need to put it by yourself: {window_ids}')
                            return

                        input_options |= window_options

                    except Exception as e:
                        cfg_mgr.logger.error(f'Not able to retrieve Window ID (hWnd) : {e}')
                        return


            cfg_mgr.logger.debug(f'Options passed to av: {input_options}')

        elif capture_methode == 'mss' and self.viinput.lower().startswith('win='):
            # for mss we need only the window name
            mss_window_name = self.viinput[4:]

        """
        viinput can be:
                    desktop or :0 ...  : to stream full screen or a part of the screen
                    title=<window name> : to stream only window content for win
                    window_id : to stream only window content for Linux 
                    queue to read np frame from a ShareAbleList (e.g: coldtype)           
                    or str
        """

        t_viinput = self.viinput

        if capture_methode == 'av':
            if sys.platform.lower() == 'win32':
                if self.viinput in ['desktop', 'area']:
                    t_viinput = 'desktop'
            elif sys.platform.lower() == 'linux':
                if self.viinput in ['area'] or self.viinput.lower().startswith('win='):
                    t_viinput = os.getenv('DISPLAY')

        win_name = f"{Utils.get_server_port()}-{t_name}-{str(t_viinput)}"

        # Open av input container in read mode if not SL and not mss
        if sl_queue is None and capture_methode == 'av':
            try:

                input_container = av.open(t_viinput, 'r', format=self.viformat, options=input_options)

            except Exception as error:
                cfg_mgr.logger.error(traceback.format_exc())
                cfg_mgr.logger.error(f'{t_name} An exception occurred: {error}')
                return

            # Decoding with auto threading...if True Decode using both FRAME and SLICE methods
            if str2bool(cfg_mgr.desktop_config['multi_thread']) is True:
                input_container.streams.video[0].thread_type = "AUTO"  # Go faster!

        # Define Output via av only if protocol is other
        if 'other' in self.protocol:
            try:

                # Output video in case of UDP or other
                output_options = {}
                output_container = av.open(self.vooutput, 'w', format=self.voformat)
                output_stream = output_container.add_stream(self.vo_codec, rate=self.rate, options=output_options)
                output_stream.width = t_scale_width
                output_stream.height = t_scale_height
                output_stream.pix_fmt = 'yuv420p'

                if str2bool(cfg_mgr.desktop_config['multi_thread']) is True:
                    output_stream.thread_type = "AUTO"

            except Exception as error:
                cfg_mgr.logger.error(traceback.format_exc())
                cfg_mgr.logger.error(f'{t_name} An exception occurred: {error}')
                return

        """
        Record

        out_file = None

        if self.record:
            out_file = iio.imopen(self.output_file, "w", plugin="pyav")
            out_file.init_video_stream(self.vo_codec, fps=frame_interval)


        End Record
        """

        # List to keep all running cast objects
        CASTDesktop.cast_names.append(t_name)
        CASTDesktop.count += 1

        start_time = time.time()

        #
        # Main loop
        #
        if input_container is not None or sl_queue is not None or capture_methode == 'mss':

            cfg_mgr.logger.info(f"{t_name} Capture from {t_viinput}")
            cfg_mgr.logger.debug(f"{t_name} Stopcast value : {self.stopcast}")
            cfg_mgr.logger.debug(f"{t_name} used methode : {capture_methode}")

            # Main frame loop
            # Stream loop
            try:

                if input_container is not None:
                    # input video stream from container (for decode)
                    input_stream = input_container.streams.get(video=0)

                    try:
                        for frame in input_container.decode(input_stream):

                            """
                            if self.record and out_file is None:
                                out_file = iio.imopen(self.output_file, "w", plugin="pyav")
                                out_file.init_video_stream(self.vo_codec, fps=frame_interval)
                            """

                            """
                            instruct the thread to exit 
                            """
                            # if global stop or local stop
                            if self.stopcast or t_todo_stop:
                                raise ExitFromLoop

                            if CASTDesktop.t_exit_event.is_set():
                                raise ExitFromLoop
                            """
                            """

                            frame_count += 1
                            CASTDesktop.total_frame += 1

                            if output_container:
                                # we send frame to output only if it exists, here only for test, this bypass ddp etc ...
                                # Convert the frame to rgb format
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

                                # resize to requested size
                                frame = frame.reformat(t_scale_width, t_scale_height)

                                # convert frame to np array
                                frame = frame.to_ndarray(format="rgb24")

                                # process frame
                                frame, grid = process_frame(frame)

                                # preview on fixed size window and receive back value from keyboard
                                if t_preview:
                                    # create ShareableList if necessary
                                    if frame_count == 1 and str2bool(cfg_mgr.app_config['preview_proc']):
                                        sl, sl_process = create_preview_sl(frame, grid)
                                        if sl is None or sl_process is None:
                                            cfg_mgr.logger.error(f'{t_name} Error on SharedList creation')
                                            raise ExitFromLoop

                                    t_preview, t_todo_stop = show_preview(frame, t_preview, t_todo_stop, grid)

                            # check here as frame is an array now
                            if CASTDesktop.t_todo_event.is_set():
                                t_preview, t_todo_stop = do_action(frame,t_preview,t_todo_stop)

                    except av.BlockingIOError as av_err:
                        if sys.platform.lower() != 'darwin':
                            cfg_mgr.logger.error(f'{t_name} An exception occurred: {av_err}')

                elif sl_queue is not None:

                    cfg_mgr.logger.debug('process from ShareAbleList-queue')
                    # Default image to display when no more frame
                    default_img = cv2.imread(cfg_mgr.app_root_path('assets/Source-intro.png'))
                    default_img = cv2.cvtColor(default_img, cv2.COLOR_BGR2RGB)
                    default_img = CV2Utils.resize_image(default_img, 640, 360, keep_ratio=False)
                    frame = default_img
                    #
                    # create ShareableList for preview if necessary
                    #
                    if t_preview and str2bool(cfg_mgr.app_config['preview_proc']):
                        sl, sl_process = create_preview_sl(i_frame=frame, i_grid=False)
                        if sl is None or sl_process is None:
                            cfg_mgr.logger.error(f'{t_name} Error on SharedList creation for Preview')
                            raise ExitFromLoop

                    # infinite loop for queue-ShareAbleList
                    while sl_queue:

                        # check to see if something to do
                        if CASTDesktop.t_todo_event.is_set():
                            t_preview, t_todo_stop = do_action(frame,t_preview,t_todo_stop)

                        """
                        instruct the thread to exit 
                        """
                        # if global stop or local stop
                        if self.stopcast or t_todo_stop:
                            raise ExitFromLoop

                        if CASTDesktop.t_exit_event.is_set():
                            raise ExitFromLoop
                        """
                        """
                        #
                        # we read data from the ShareAbleList
                        #
                        time_frame = sl_queue[1]
                        # check if recent frame that we need to proces (some frames can be skipped in busy system)
                        # this adds also 2s delay before display default image
                        if time_frame + 2 > time.time():
                            # ShareAbleList bug
                            frame = CV2Utils.frame_remove_one(sl_queue[0])
                            # process frame
                            # 1D array
                            frame = np.frombuffer(frame, dtype=np.uint8)
                            # 2D array
                            if frame.nbytes > 0:
                                # rgb
                                frame = frame.reshape(int(t_scale_width), int(t_scale_height), 3)
                                #
                                frame_count += 1
                                CASTDesktop.total_frame += 1
                                #
                                frame, grid = process_frame(frame)
                                #
                                if t_preview:
                                    t_preview, t_todo_stop = show_preview(frame, t_preview, t_todo_stop, grid)

                            else:
                                cfg_mgr.logger.debug('skip frame of size = 0')
                        else:
                            # preview default image
                            if t_preview:
                                t_preview, t_todo_stop = show_preview(default_img,
                                                                         t_preview,
                                                                         t_todo_stop,
                                                                         i_grid=False)

                        # some sleep until next, this could add some delay to stream next available frame
                        time.sleep(0.1)

                elif capture_methode == 'mss':

                    with mss.mss() as sct:

                        if t_viinput == 'area':

                            # specific area
                            # Calculate crop parameters : ; 19/06/2024 coordinates for 2 monitor need to be reviewed
                            x1 = int(self.screen_coordinates[0])
                            y1 = int(self.screen_coordinates[1])
                            x2 = int(self.screen_coordinates[2])
                            y2 = int(self.screen_coordinates[3])
                            # Define the screen region to capture
                            # monitor = {"top": 100, "left": 100, "width": 800, "height": 600}
                            sc_monitor = {'top': y1, 'left': x1, 'width': x2 - x1, 'height': y2 - y1}

                        elif t_viinput == 'desktop':

                            # Get monitor dimensions for full-screen capture
                            # [0] is the virtual screen, [1] is the primary monitor [2] second one
                            monitor += 1
                            sc_monitor = sct.monitors[monitor]


                        elif t_viinput.lower().startswith('win='):

                            rect = Utils.get_window_rect(mss_window_name)

                            if rect:
                                left, top, width, height = rect
                                sc_monitor = {"top": top, "left": left, "width": width, "height": height}

                            else:
                                cfg_mgr.logger.error(f"Window '{mss_window_name}' not found.")
                                raise ExitFromLoop

                        else:
                            cfg_mgr.logger.error('Not available with mss')
                            raise ExitFromLoop

                        while True:

                            # Calculate the expected time for the current frame
                            expected_time = start_time + frame_count * interval

                            # check to see if something to do
                            if CASTDesktop.t_todo_event.is_set():
                                t_preview, t_todo_stop = do_action(frame, t_preview, t_todo_stop)

                            """
                            instruct the thread to exit 
                            """
                            # if global stop or local stop
                            if self.stopcast or t_todo_stop:
                                raise ExitFromLoop

                            if CASTDesktop.t_exit_event.is_set():
                                raise ExitFromLoop
                            """
                            """

                            # Capture full-screen
                            frame = sct.grab(sc_monitor)

                            # Convert to NumPy array and format for OpenCV
                            frame = np.array(frame)  # RGBA format

                            frame_count += 1
                            CASTDesktop.total_frame += 1
                            #
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                            frame, grid = process_frame(frame)

                            #
                            if t_preview:
                                # create ShareableList if necessary
                                if frame_count == 1 and str2bool(cfg_mgr.app_config['preview_proc']):
                                    sl, sl_process = create_preview_sl(frame, grid)
                                    if sl is None or sl_process is None:
                                        cfg_mgr.logger.error(f'{t_name} Error on SharedList creation')
                                        raise ExitFromLoop

                                t_preview, t_todo_stop = show_preview(frame, t_preview, t_todo_stop, grid)

                            need_to_sleep()

                else:
                    cfg_mgr.logger.error(f'Do not know what to do from this input: {t_viinput}')
                    raise ExitFromLoop

            except ExitFromLoop as ext:
                cfg_mgr.logger.info(f'{t_name} Requested to end cast loop {ext}')

            except Exception as e:
                cfg_mgr.logger.error(traceback.format_exc())
                cfg_mgr.logger.error(f'{t_name} An exception occurred: {e}')

            finally:
                """
                END
                """
                # close av input
                if input_container is not None:
                    input_container.close()
                    cfg_mgr.logger.info(f'{t_name} AV Input container closed')
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
                    CV2Utils.cv2_win_close(port, 'Desktop', t_name, t_viinput)
        else:

            cfg_mgr.logger.error(f'{t_name} av input_container not defined or no queue')

        """
        END +
        """

        CASTDesktop.count -= 1
        CASTDesktop.cast_names.remove(t_name)
        CASTDesktop.t_exit_event.clear()

        if capture_methode == 'mss':
            sct.close()

        # Clean ShareableList
        Utils.sl_clean(sl, sl_process, t_name)

        # stop e131/artnet
        if t_protocol == 'e131':
            e131_host.deactivate()
        elif t_protocol == 'artnet':
            artnet_host.deactivate()

        # cleanup SL
        if sl_queue is not None:
            sl_client.delete_shared_list(sl_name_q)
            # check if last SL
            sl_list = ast.literal_eval(sl_client.get_shared_lists())
            if len(sl_list) == 0:
                # stop manager
                sl_manager.stop_manager()

        cfg_mgr.logger.debug("_" * 50)
        cfg_mgr.logger.debug(f'Cast {t_name} end using this input: {t_viinput}')
        cfg_mgr.logger.debug(f'Using these devices: {ip_addresses}')
        cfg_mgr.logger.debug("_" * 50)

        cfg_mgr.logger.info(f'{t_name} Cast closed')

    def cast(self, shared_buffer=None, log_ui=None):
        """
            this will run the cast into another thread
            avoiding blocking the main one
            shared_buffer: if used need to be a queue
            log_ui : logger to send data to main logger on root page
        """
        if log_ui is not None:
            root_logger = cfg_mgr.logger.getLogger()
            if log_ui not in root_logger:
                cfg_mgr.logger.addHandler(log_ui)
        thread = threading.Thread(target=self.t_desktop_cast, args=(shared_buffer,Utils.get_server_port()))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        cfg_mgr.logger.debug('Child Desktop cast initiated')
