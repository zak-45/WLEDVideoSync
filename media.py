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
# A preview can be seen via 'cv2' : pixelart look
#
import logging
import logging.config

import cv2
import time

import threading
from threading import current_thread
import asyncio
import concurrent.futures

from ddp import DDPDevice
from utils import CASTUtils as Utils, LogElementHandler

# read config
logging.config.fileConfig('config/logging.ini')
# create logger
logger = logging.getLogger('WLEDLogger.media')

t_send_frame = threading.Event()  # thread listen event to send frame via ddp (for synchro used by multicast)
t_media_lock = threading.Lock()  # define lock for to do

"""
MultiCast
"""


def send_multicast_image(ip, image):
    """
    This sends an image to an IP address using DDP, used by multicast
    :param ip:
    :param image:
    :return:
    """
    # timeout provided to not have thread waiting infinitely
    if t_send_frame.wait(timeout=.1):
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
        multicast = [executor.submit(send_multicast_image, ip, image)
                     for ip, image in zip(ip_addresses, images_buffer)]

        # once all threads up, need to set event because they wait for
        t_send_frame.set()

        # Wait for all threads to complete
        concurrent.futures.wait(multicast, timeout=1)

    t_send_frame.clear()


"""
Class definition
"""


class CASTMedia:
    """ Cast Media to DDP """

    count = 0  # initialise count to zero

    t_exit_event = threading.Event()  # thread listen event fo exit
    t_info_event = threading.Event()  # thread listen event for info
    t_todo_event = threading.Event()  # thread listen event for task to do

    def __init__(self):
        self.rate: int = 25
        self.stopcast: bool = True
        self.preview: bool = True
        self.scale_width: int = 640
        self.scale_height: int = 480
        self.wled: bool = False
        self.wled_live = False
        self.host: str = "127.0.0.1"
        self.port: int = 4048
        self.protocol: str = "ddp"
        self.retry_number: int = 0
        self.viinput: int = 0
        self.keep_ratio: bool = True
        self.flip: bool = False
        self.flip_vh: int = 0
        self.frame_buffer = []
        self.frame_index: int = 0
        self.put_to_buffer: bool = False
        self.frame_max: int = 8
        self.text: bool = False
        self.custom_text: str = ""
        self.multicast: bool = False
        self.cast_x: int = 1
        self.cast_y: int = 1
        self.cast_devices: list = []
        self.cast_frame_buffer = []
        self.cast_name_todo = []  # list of thread names with action that need to execute 'to do'

    """
    Cast Thread
    """

    def t_media_cast(self, shared_buffer=None):
        """
            Main cast logic
            Cast media : video file, image file or video capture device
        """
        t_name = current_thread().name
        logger.info(f'Child thread: {t_name}')

        start_time = time.time()
        t_preview = self.preview
        t_multicast = self.multicast
        t_cast_x = self.cast_x
        t_cast_y = self.cast_y

        frame_count = 0
        frame_interval = 1.0 / self.rate  # Calculate the time interval between frames

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
        t_viinput = self.viinput

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

        ip_addresses.append(self.host)

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
                        asyncio.run(Utils.put_wled_live(cast_ip, on=True, live=True, timeout=1))
                    ip_addresses.append(cast_ip)
                    logger.info(f'IP : {cast_ip} for sub image number {i}')

        CASTMedia.count += 1

        """
        Second, capture media
        """

        self.frame_buffer = []
        self.cast_frame_buffer = []
        t_frame_buffer = []
        t_cast_frame_buffer = []

        # capture media
        media = cv2.VideoCapture(t_viinput)
        # Check if the capture is successful
        if not media.isOpened():
            logger.error(f"Error: Unable to open media stream {t_viinput}.")
            CASTMedia.count -= 1
            return False

        media.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        length = int(media.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = media.get(cv2.CAP_PROP_FPS)

        logger.info(f"Playing media {t_viinput} of length {length} at {fps} FPS")

        # detect if we want specific frame index: only for non-live video
        if self.frame_index != 0 and length != -1:
            logger.info(f"Take frame number {self.frame_index}")
            media.set(1, self.frame_index - 1)

        """
            Media Loop
        """

        last_frame = time.time()

        # Main thread loop to read media frame, stop from global call or local
        while not self.stopcast and not t_todo_stop:
            """
            instruct the thread to exit 
            """
            if CASTMedia.t_exit_event.is_set():
                break

            """
            instruct the thread to provide info 
            """
            if CASTMedia.t_info_event.is_set():

                if shared_buffer is None:
                    logger.warning('No queue buffer defined')
                    CASTMedia.t_info_event.clear()
                else:
                    t_info = {t_name: {"type": "info", "data": {"start": start_time,
                                                                "tid": current_thread().native_id,
                                                                "viinput": str(t_viinput),
                                                                "multicast": t_multicast,
                                                                "devices": ip_addresses,
                                                                "frames": frame_count
                                                                }}}
                    shared_buffer.put(t_info)

            #  read media
            success, frame = media.read()
            if not success:
                logger.warning('Error to read media or reached END')
                break

            # flip vertical/horizontal: 0,1,2
            if self.flip:
                frame = cv2.flip(frame, self.flip_vh)

            # convert to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            """
            check if something to do
            manage concurrent access to the list by using lock feature
            event clear only when no more item in list
            """
            if CASTMedia.t_todo_event.is_set():
                t_media_lock.acquire()

                #  take thread name from cast list
                for item in self.cast_name_todo:
                    name, action, added_time = item.split('||')
                    if name == t_name:
                        logging.info(f'To do: {action} for :{t_name}')

                        try:
                            if 'stop' in action:
                                t_todo_stop = True
                            elif 'buffer' in action:
                                add_frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)
                                add_frame = Utils.resize_image(add_frame, 640, 480)
                                self.frame_buffer.append(add_frame)
                                if t_multicast:
                                    # resize frame to virtual matrix size
                                    add_frame = Utils.resize_image(frame,
                                                                   self.scale_width * t_cast_x,
                                                                   self.scale_height * t_cast_y)

                                    self.cast_frame_buffer = Utils.split_image_to_matrix(add_frame,
                                                                                         t_cast_x, t_cast_y)

                        except:
                            # self.cast_name_todo.remove(item)
                            # t_media_lock.release()
                            logger.error(f'Action {action} in ERROR from {t_name}')

                        self.cast_name_todo.remove(item)
                        if len(self.cast_name_todo) == 0:
                            CASTMedia.t_todo_event.clear()

                t_media_lock.release()

            frame_count += 1

            if not t_multicast:
                # resize frame for sending to ddp device
                frame_to_send = Utils.resize_image(frame, self.scale_width, self.scale_height)
                # resize frame to pixelart
                frame = Utils.pixelart_image(frame, self.scale_width, self.scale_height)

                # send to DDP
                if self.protocol == "ddp":
                    ddp.flush(frame_to_send, self.retry_number)

                # put frame to np buffer (so can be used after by the main)
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

                    # Displaying the image
                    cv2.imshow("Media Preview input: " + str(t_viinput), frame)
                    cv2.resizeWindow("Media Preview input: " + str(t_viinput), 640, 480)
                    if cv2.waitKey(10) & 0xFF == ord("q"):
                        win = cv2.getWindowProperty("Media Preview input: " + str(t_viinput), cv2.WND_PROP_VISIBLE)
                        if win != 0:
                            cv2.destroyWindow("Media Preview input: " + str(t_viinput))

                """
                    stop for non-live video (length not -1)
                    if we reach end of video or request only one frame from index
                """
                if length != -1:
                    if frame_count >= length or self.frame_index != 0:
                        logger.info("Reached END ...")
                        break
            else:
                """
                    multicast manage any number of devices of same configuration
                    each device need to drive the same amount of leds, same config
                    e.g. WLED matrix 16x16 : 3(x) x 2(y)                    
                    ==> this give 5 devices to set into cast_devices list (host is auto incl. and will be the first one)                        
                        (tuple of: device index(0...n) , IP address) 
                        we will manage image of 3x16 leds for x and 2x16 for y    
                        
                    on 10/04/2024: device_number come from list entry order (0...n)
                        
                """

                # resize frame to virtual matrix size
                frame = Utils.resize_image(frame,
                                           self.scale_width * t_cast_x,
                                           self.scale_height * t_cast_y)

                # populate global cast buffer from first frame only
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
                    logger.error('An exception occurred: {}'.format(error))
                    break

            """
            do we need to sleep
            """
            delay = time.time() - last_frame
            # sleep depend of the interval (FPS)
            if delay < frame_interval:
                time.sleep(frame_interval - delay)

            last_frame = time.time()

        """
            Final : End Media Loop
        """

        CASTMedia.count -= 1

        if CASTMedia.count <= 2:  # try to avoid blocking when click as a bad man !!!
            logger.info('Stop window preview if any')
            time.sleep(1)
            win = cv2.getWindowProperty("Media Preview input: " + str(t_viinput), cv2.WND_PROP_VISIBLE)
            if win != 0:
                cv2.destroyWindow("Media Preview input: " + str(t_viinput))

        media.release()

        print("_" * 50)
        print(f'Cast {t_name} end using this media: {t_viinput}')
        print(f'Using these devices: {str(ip_addresses)}')
        print("_" * 50)

        logger.info("Cast closed")
        CASTMedia.t_exit_event.clear()

        time.sleep(2)

    def cast(self, shared_buffer=None):
        """
            this will run the cast into another thread
            avoid to block the main one
        """
        thread = threading.Thread(target=self.t_media_cast, args=(shared_buffer,))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        logger.info('Child Media cast running')
