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
# You can cast your entire desktop screen or only window content.
# Data will be sent through 'ddp' protocol or stream via udp:// rtp:// etc ...
#
#
import logging
import logging.config
import traceback

import time
import av
import cv2

import threading
from threading import current_thread
import asyncio
import concurrent.futures

from ddp_async import DDPDevice
from utils import CASTUtils as Utils, LogElementHandler

# read config
logging.config.fileConfig('config/logging.ini')
# create logger
logger = logging.getLogger('WLEDLogger.desktop')


class CASTDesktop:
    """ Cast Desktop to DDP """

    count = 0  # initialise count to zero

    t_exit_event = threading.Event()  # thread listen event
    t_info_event = threading.Event()  # thread listen event for info
    t_todo_event = threading.Event()  # thread listen event for task to do
    t_desktop_lock = threading.Lock()  # define lock for to do

    def __init__(self):
        self.rate: int = 25
        self.stopcast: bool = True
        self.scale_width: int = 128
        self.scale_height: int = 128
        self.flip_vh = 0
        self.flip = False
        self.wled: bool = False
        self.wled_live = False
        self.host: str = '127.0.0.1'
        self.port: int = 4048
        self.protocol: str = 'ddp'  # put 'other' to use vooutput
        self.retry_number: int = 0  # number of time to resend ddp packet
        self.viformat: str = 'gdigrab'  # 'gdigrab' for win
        self.viinput = 'desktop'  # 'desktop' full screen or 'title=<window title>'
        self.preview = True
        self.text = False
        self.custom_text: str = ""
        self.voformat: str = 'h264'
        self.vooutput: str = 'udp://127.0.0.1:12345?pkt_size=1316'
        self.active: bool = False
        self.put_to_buffer: bool = False
        self.frame_buffer: list = []
        self.frame_max: int = 8
        self.multicast: bool = False
        self.cast_x: int = 1
        self.cast_y: int = 1
        self.cast_devices: list = []
        self.cast_frame_buffer = []
        self.cast_name_todo = []  # list of thread names that need to execute to do

    def t_desktop_cast(self, shared_buffer=None):
        """
            Cast desktop screen or a window content based on the title
            With big size image, some delay occur, to do : review 'ddp.flush' when necessary
        """
        t_name = current_thread().name
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
            if t_send_frame.wait(timeout=.1):
                # send ddp data
                device = DDPDevice(ip)
                asyncio.run(device.flush(image))
            else:
                logger.warning('Multicast frame dropped')

        def send_multicast_images_to_ips(images_buffer, to_ip_addresses):
            """
            Create a thread for each image , IP pair and wait for all to finish
            Very simple synchro process
            :param images_buffer:
            :param to_ip_addresses:
            :return:
            """
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Submit a thread for each image and IP pair
                multicast = [executor.submit(send_multicast_image, ip, image)
                             for ip, image in zip(to_ip_addresses, images_buffer)]

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
                logger.info(f'We work with this IP {self.host} as first device: number 0')
            else:
                logger.error(f'Error looks like IP {self.host} do not accept connection to port 80')
                return False

        # retrieve matrix setup from wled and set w/h
        if self.wled:
            status = asyncio.run(Utils.put_wled_live(self.host, on=True, live=True, timeout=1))
            if status:
                self.scale_width, self.scale_height = asyncio.run(Utils.get_wled_matrix_dimensions(self.host))
            else:
                logger.error(f"ERROR to set WLED device {self.host} on 'live' mode")
                return False

        ddp = DDPDevice(self.host)

        # specifics for Multicast
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
                    Utils.check_ip_alive(cast_ip, port=80, timeout=2)
                    if self.wled:
                        status = asyncio.run(Utils.put_wled_live(cast_ip, on=True, live=True, timeout=1))
                        if not status:
                            logger.error(f"ERROR to set WLED device {self.host} on 'live' mode")
                            return False

                    ip_addresses.append(cast_ip)
                    logger.info(f'IP : {cast_ip} for sub image number {i}')
        else:

            ip_addresses.append(self.host)

        CASTDesktop.count += 1

        """
        Second, capture media
        """

        self.frame_buffer = []
        self.cast_frame_buffer = []
        frame_interval = self.rate

        # Open video device (desktop / window)
        input_options = {'c:v': 'libx264rgb', 'crf': '0', 'preset': 'ultrafast', 'pix_fmt': 'rgb24',
                         'framerate': str(frame_interval), 'probesize': '100M'}
        input_format = self.viformat

        """
        viinput can be:
                    desktop : to stream full screen
                    title=<window name> : to stream only window content
        """
        t_viinput = self.viinput

        # Open av input container in read mode
        try:

            input_container = av.open(t_viinput, 'r', format=input_format, options=input_options)

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error('An exception occurred: {}'.format(error))
            CASTDesktop.count -= 1
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
                logger.error('An exception occurred: {}'.format(error))
                CASTDesktop.count -= 1
                return False

        # Main loop
        if input_container:
            # input video stream from container (for decode)
            input_stream = input_container.streams.get(video=0)

            # Main frame loop
            # Stream loop
            try:

                logger.info(f"Capture from {t_viinput}")
                for frame in input_container.decode(input_stream):

                    frame_count += 1

                    # if global stop or local stop
                    if self.stopcast or t_todo_stop:
                        break

                    """
                    instruct the thread to exit 
                    """
                    if CASTDesktop.t_exit_event.is_set():
                        break

                    if not output_container:
                        # convert frame to np array
                        frame = frame.to_ndarray(format="rgb24")

                        # flip vertical/horizontal: 0,1,2
                        if self.flip:
                            frame = cv2.flip(frame, self.flip_vh)

                        """
                        check if something to do
                        manage concurrent access to the list by using lock feature
                        event clear only when no more item in list
                        """
                        if CASTDesktop.t_todo_event.is_set():
                            logger.info('inside todo ')
                            CASTDesktop.t_desktop_lock.acquire()
                            #  take thread name from cast to do list
                            for item in self.cast_name_todo:
                                name, action, added_time = item.split('||')
                                if name == t_name:
                                    logging.info(f'To do: {action} for :{t_name}')

                                    # use try to capture any failure
                                    try:
                                        if 'stop' in action:
                                            t_todo_stop = True
                                        elif 'buffer' in action:
                                            add_frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                                            add_frame = Utils.resize_image(add_frame, self.scale_width,
                                                                           self.scale_height)
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
                                                                                        "fps": frame_interval,
                                                                                        "frames": frame_count
                                                                                        }}}
                                            # this wait until queue access is free
                                            shared_buffer.put(t_info)
                                            logger.info('we have put')

                                        elif "close_preview" in action:
                                            win = cv2.getWindowProperty("Desktop Preview input: " + str(t_viinput),
                                                                        cv2.WND_PROP_VISIBLE)
                                            if not win == 0:
                                                cv2.destroyWindow("Desktop Preview input: " + str(t_viinput))
                                            t_preview = False

                                    except:
                                        logger.error(traceback.format_exc())
                                        logger.error(f'Action {action} in ERROR from {t_name}')

                                    self.cast_name_todo.remove(item)
                                    if len(self.cast_name_todo) == 0:
                                        CASTDesktop.t_todo_event.clear()

                            CASTDesktop.t_desktop_lock.release()

                        if not t_multicast:
                            # resize frame for sending to ddp device
                            frame_to_send = Utils.resize_image(frame, self.scale_width, self.scale_height)
                            # resize frame to pixelart
                            frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)

                            # send to ddp device
                            if self.protocol == 'ddp':
                                asyncio.run(ddp.flush(frame_to_send, self.retry_number))

                            # save frame to np buffer if requested (so can be used after by the main)
                            if self.put_to_buffer and frame_count <= self.frame_max:
                                self.frame_buffer.append(frame)

                            # preview on fixed size window
                            if t_preview:

                                frame = cv2.resize(frame, (640, 480))
                                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                                # put text on the image
                                if self.text:
                                    if self.custom_text == "":
                                        text_to_show = "WLEDVideoSync"
                                    else:
                                        text_to_show = self.custom_text
                                    # font
                                    font = cv2.FONT_HERSHEY_SIMPLEX
                                    # org
                                    org = (50, 50)
                                    # fontScale
                                    fontscale = .5
                                    # Blue color in BGR
                                    color = (255, 0, 0)
                                    # Line thickness of 2 px
                                    thickness = 2
                                    # Using cv2.putText() method
                                    frame = cv2.putText(frame,
                                                        text_to_show,
                                                        org,
                                                        font,
                                                        fontscale,
                                                        color,
                                                        thickness,
                                                        cv2.LINE_AA)

                                # Displaying the image on the preview Window
                                cv2.imshow("Desktop Preview input: " + str(t_viinput), frame)
                                cv2.resizeWindow("Desktop Preview input: " + str(t_viinput), 640, 480)
                                if cv2.waitKey(10) & 0xFF == ord("q"):
                                    cv2.destroyWindow("Desktop Preview input: " + str(t_viinput))
                                    # close preview window if any
                                    win = cv2.getWindowProperty("Desktop Preview input: " + str(t_viinput),
                                                                cv2.WND_PROP_VISIBLE)
                                    if not win == 0:
                                        cv2.destroyWindow("Desktop Preview input: " + str(t_viinput))
                                    t_preview = False

                        else:
                            """
                                multicast manage any number of devices of same configuration
                                each device need to drive the same amount of leds, same config
                                e.g. WLED matrix 16x16 : 3(x) x 2(y)                    
                                ==> this give 5 devices to set into cast_devices list (host is auto incl.)                    
                                    (tuple of: device index(0...n) , IP address) 
                                    we will manage image of 3x16 leds for x and 2x16 for y    

                                on 10/04/2024: device_number come from list entry order (0...n)

                            """

                            # resize frame to virtual matrix size
                            frame = Utils.resize_image(frame,
                                                       self.scale_width * t_cast_x,
                                                       self.scale_height * t_cast_y)

                            if frame_count > 1:
                                # split to matrix
                                t_cast_frame_buffer = Utils.split_image_to_matrix(frame, t_cast_x, t_cast_y)

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
                                logger.error('An exception occurred: {}'.format(error))
                                break
                    else:

                        # we send frame to output only if it exists, here only for test, this bypass ddp etc ...
                        # Encode the frame
                        packet = output_stream.encode(frame)
                        # Mux the encoded packet
                        output_container.mux(packet)

            except Exception as error:
                logger.error(traceback.format_exc())
                logger.error('An exception occurred: {}'.format(error))

            finally:
                """
                END
                """
                # close av input
                input_container.close()
                # close av output if any
                if output_container:
                    output_container.close()
                if CASTDesktop.count <= 2:  # try to avoid to block if more casts thread and preview True
                    logger.info('Stop window preview if any')
                    time.sleep(1)
                    # close preview window if any
                    win = cv2.getWindowProperty("Desktop Preview input: " + str(t_viinput), cv2.WND_PROP_VISIBLE)
                    if not win == 0:
                        cv2.destroyWindow("Desktop Preview input: " + str(t_viinput))

        else:

            logger.warning('av input_container not defined')

        """
        END +
        """

        CASTDesktop.count -= 1

        print("_" * 50)
        print(f'Cast {t_name} end using this input: {t_viinput}')
        print(f'Using these devices: {str(ip_addresses)}')
        print("_" * 50)

        logger.info('Cast closed')
        time.sleep(2)
        CASTDesktop.t_exit_event.clear()

    def cast(self, shared_buffer=None):
        """
            this will run the cast into another thread
            avoiding blocking the main one
        """
        thread = threading.Thread(target=self.t_desktop_cast, args=(shared_buffer,))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        logger.info('Child Desktop cast initiated')
