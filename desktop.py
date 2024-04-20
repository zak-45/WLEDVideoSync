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

import time
import av
import cv2

import threading
from threading import current_thread
import asyncio
import concurrent.futures

from ddp import DDPDevice
from utils import CASTUtils as Utils, LogElementHandler

# read config
logging.config.fileConfig('config/logging.ini')
# create logger
logger = logging.getLogger('WLEDLogger.desktop')

t_send_frame = threading.Event()  # thread listen event to send frame via ddp


def send_multicast_image(ip, image):
    """
    This sends an image to an IP address using DDP
    :param ip:
    :param image:
    :return:
    """
    # timeout provided to not have thread waiting infinitely
    if t_send_frame.wait(timeout=1):
        # send ddp data
        device = DDPDevice(ip)
        device.flush(image)
    else:
        logger.warning('Multicast frame dropped')


def send_multicast_images_to_ips(images_buffer, ip_addresses):
    """
    Create a thread for each image , IP pair and wait for all to finish
    Very simple synchro process
    :param images_buffer:
    :param ip_addresses:
    :return:
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit a thread for each image and IP pair
        futures = [executor.submit(send_multicast_image, ip, image)
                   for ip, image in zip(ip_addresses, images_buffer)]

        # once all threads up, need to set event because they wait for
        t_send_frame.set()

        # Wait for all threads to complete
        concurrent.futures.wait(futures)

    t_send_frame.clear()


class CASTDesktop:
    """ Cast Desktop to DDP """

    count = 0  # initialise count to zero
    t_exit_event = threading.Event()  # thread listen event
    t_provide_info = threading.Event()  # thread listen event for info

    def __init__(self):
        self.rate: int = 25
        self.stopcast: bool = True
        self.scale_width: int = 640
        self.scale_height: int = 480
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

    def t_desktop_cast(self, shared_buffer=None):
        """
            Cast desktop screen or a window content based on the title
        """
        t_name = current_thread().name
        logger.info(f'Child thread: {t_name}')

        CASTDesktop.count += 1

        start_time = time.time()

        """
        Cast devices
        """
        ip_addresses = []
        cast_ip_addresses = []

        """
        av 
        """
        output_container = False
        output_stream = None

        ddp = DDPDevice(self.host)

        self.frame_buffer = []
        frame_count = 0

        # if wled device, autodetect matrix settings (x and y)
        if self.wled:
            self.scale_width, self.scale_height = asyncio.run(Utils.get_wled_matrix_dimensions(self.host))

        # specifics for Multicast
        if self.multicast:
            # validate cast_devices list
            if not Utils.is_valid_cast_device(str(self.cast_devices)):
                logger.error("Error Cast device list not compliant to format [(0,'xx.xx.xx.xx')...]")
                CASTDesktop.count -= 1
                return False
            else:
                logger.info('Virtual Matrix size is :' +
                            str(self.scale_width * self.cast_x) + 'x' + str(self.scale_height * self.cast_y))
                # populate ip_addresses list
                for i in range(len(self.cast_devices)):
                    cast_ip = self.cast_devices[i][1]
                    Utils.check_ip_alive(cast_ip, port=80, timeout=2)
                    if self.wled:
                        asyncio.run(Utils.put_wled_live(cast_ip, on=True, live=True, timeout=1))
                    ip_addresses.append(cast_ip)
                    cast_ip_addresses.append(cast_ip)
                    logger.info(f'IP : {cast_ip} for sub image number {i}')

        # Open video device (desktop / window)
        input_options = {'c:v': 'libx264rgb', 'crf': '0', 'preset': 'ultrafast', 'pix_fmt': 'rgb24',
                         'framerate': str(self.rate), 'probesize': '100M'}
        input_format = self.viformat

        """
        viinput can be:
                    desktop : to stream full screen
                    title=<window name> : to stream only window content
        """
        input_filename = self.viinput

        # Open av input container in read mode
        try:

            input_container = av.open(input_filename, 'r', format=input_format, options=input_options)

        except Exception as error:

            logger.error('An exception occurred: {}'.format(error))
            CASTDesktop.count -= 1
            return False

        # Output via av only if protocol is other
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

                logger.info(f"Capture from {input_filename}")
                for frame in input_container.decode(input_stream):
                    """
                    instruct the thread to exit 
                    """
                    if CASTDesktop.t_exit_event.is_set():
                        break

                    if self.stopcast:
                        break

                    frame_count += 1
                    """
                    # resize the frame
                    frame = frame.reformat(self.scale_width, self.scale_height)
                    """

                    # we send frame to output only if exist
                    if output_container:
                        # Encode the frame
                        packet = output_stream.encode(frame)
                        # Mux the encoded packet
                        output_container.mux(packet)

                    else:

                        # convert frame to np array
                        frame = frame.to_ndarray(format="rgb24")

                        # flip vertical/horizontal: 0,1,2
                        if self.flip:
                            frame = cv2.flip(frame, self.flip_vh)

                        if not self.multicast:
                            # resize frame for sending to ddp device
                            frame_to_send = Utils.resize_image(frame, self.scale_width, self.scale_height)
                            # resize frame to pixelart
                            frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)

                            # send to ddp device
                            if self.protocol == 'ddp':
                                ddp.flush(frame_to_send, self.retry_number)

                            # save frame to np buffer if requested (so can be used after by the main)
                            if self.put_to_buffer and frame_count <= self.frame_max:
                                self.frame_buffer.append(frame)

                            # preview on fixed size window
                            if self.preview:

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
                                cv2.imshow("Desktop Preview input: " + str(self.viinput), frame)
                                cv2.resizeWindow("Desktop Preview input: " + str(self.viinput), 640, 480)
                                if cv2.waitKey(10) & 0xFF == ord("q"):
                                    self.preview = False
                                    cv2.destroyWindow("Desktop Preview input: " + str(self.viinput))
                        else:
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
                            frame = Utils.resize_image(frame,
                                                       self.scale_width * self.cast_x,
                                                       self.scale_height * self.cast_y)
                            # split to matrix
                            self.cast_frame_buffer = Utils.split_image_to_matrix(frame, self.cast_x, self.cast_y)

                            # validate cast_devices number
                            if len(self.cast_devices) != len(self.cast_frame_buffer):
                                logger.error('Cast devices number != sub images number: check cast_devices ')
                                raise Exception

                            # send, keep synchronized
                            try:

                                send_multicast_images_to_ips(self.cast_frame_buffer, cast_ip_addresses)

                            except Exception as error:
                                logger.error('An exception occurred: {}'.format(error))

                    """
                    instruct the thread to provide info 
                    """
                    if CASTDesktop.t_provide_info.is_set():

                        if shared_buffer is None:
                            logger.warning('No queue buffer defined')
                        else:
                            t_info = {t_name: {"type": "info", "data": {"start": start_time,
                                                                        "viinput": str(input_filename),
                                                                        "devices": ip_addresses,
                                                                        "frames": frame_count
                                                                        }}}
                            shared_buffer.put(t_info)

            except Exception as error:

                logger.error('An exception occurred: {}'.format(error))

            finally:

                # close av input
                input_container.close()
                # close av output if any
                if output_container:
                    output_container.close()
                # close preview window if any
                win = cv2.getWindowProperty("Desktop Preview input: " + str(self.viinput), cv2.WND_PROP_VISIBLE)
                if win != 0:
                    cv2.destroyWindow("Desktop Preview input: " + str(self.viinput))

        else:

            logger.warning('av input_container not defined')

        CASTDesktop.count -= 1

        print("_" * 50)
        print(f'Cast {t_name} end using this input: {input_filename}')
        print(f'Using these devices: {str(ip_addresses)}')
        print("_" * 50)

        logger.info('Cast closed')
        CASTDesktop.t_exit_event.clear()

        time.sleep(2)

    def cast(self, shared_buffer=None):
        """
            this will run the cast into another thread
            avoiding blocking the main one
        """
        thread = threading.Thread(target=self.t_desktop_cast, args=(shared_buffer,))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        logger.info('Child Desktop cast initiated')
