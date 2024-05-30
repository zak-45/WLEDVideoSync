"""
# a: zak-45
# d: 13/03/2024
# v: 1.0.0
#
# CASTUtils
#
#          CAST utilities
#
# pywinctl provide a cross-platform window mgt.
to avoid cv2 imshow freeze (linux)
import numpy as np
import cv2
cv2.imshow('ffmpeg fix', np.array([1], dtype=np.uint8))
cv2.destroyAllWindows()
import av
#
"""

import logging
import logging.config
import sys
import traceback

import re
import platform
import cv2
import numpy as np
import pywinctl as pwc
from wled import WLED
import av

from PIL import Image
import io
import base64

import time
import shelve
import os

import psutil
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from zeroconf import ServiceBrowser, Zeroconf
import socket
import ipaddress

from pathlib import Path
from typing import Optional

from nicegui import events, ui

from pytube import YouTube

"""
When this env var exist, this mean run from the one-file executable.
Load of the config is not possible, folder config should not exist.
This avoid FileNotFoundError.
This env not exist when run the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    # read config
    logging.config.fileConfig('config/logging.ini')
    # create logger
    logger = logging.getLogger('WLEDLogger.utils')


# do not show graph at module load, suspend interactive mode (e.g. PyCharm)
if sys.platform == 'win32':
    plt.ioff()


class CASTUtils:
    dev_list: list = []
    matrix_x: int = 0
    matrix_y: int = 0
    yt_file_name: str = ''

    def __init__(self):
        pass

    @staticmethod
    def list_formats():
        dict_formats = []
        j = 0
        for item in av.formats_available:
            dict_formats.append(item)
            j += 1
        dict_formats = sorted(dict_formats)
        return dict_formats

    @staticmethod
    def list_codecs():
        dict_codecs = []
        j = 0
        for item in av.codec.codecs_available:
            dict_codecs.append(item)
            j += 1
        dict_codecs = sorted(dict_codecs)
        return dict_codecs

    @staticmethod
    async def youtube(yt_url: str = None):
        """download video from youtube"""

        def progress_func(stream_name, data, remain_bytes):
            ui.notify('In progress from YouTube ... remaining : ' + CASTUtils.bytes2human(remain_bytes))
            logger.info('In progress from YouTube ... remaining : ' + CASTUtils.bytes2human(remain_bytes))

        def complete_func(stream_name, file_path):
            CASTUtils.yt_file_name = file_path
            ui.notify('YouTube Finished : ' + file_path)
            logger.info('YouTube Finished : ' + file_path)

        try:
            yt = YouTube(
                url=yt_url,
                on_progress_callback=progress_func,
                on_complete_callback=complete_func,
                use_oauth=False,
                allow_oauth_cache=True
            )

            # this usually should select the first 720p video, enough for cast
            prog_stream = yt.streams.filter(progressive=True).order_by('resolution').desc().first()
            # initiate download to tmp folder
            prog_stream.download(output_path='tmp', filename_prefix='yt-tmp-', timeout=3, max_retries=2)

        except Exception as error:
            CASTUtils.yt_file_name = ''
            logger.info('youtube error:', error)

        return CASTUtils.yt_file_name

    @staticmethod
    def get_server_port():
        """ Retrieve server port number """
        server_port = 0
        try:
            # server running from another process (e.g. Uvicorn)
            p_pid = os.getppid()
            tmp_file = f"./tmp/{p_pid}_file"
            if os.path.isfile(tmp_file + ".dat"):
                infile = shelve.open(tmp_file)
                server_port = infile["server_port"]
        except:
            server_port = 99

        return server_port

    @staticmethod
    async def get_wled_matrix_dimensions(host, timeout: int = 2):
        """
        Take matrix information from WLED device
        :param host:
        :param timeout:
        :return:
        """
        wled = WLED(host)
        matrix = {"w": 1, "h": 1}
        try:
            wled.request_timeout = timeout
            await wled.connect()
            if wled.connected:
                # Get WLED info's
                response = await wled.request("/json/info")
                matrix = response["leds"]["matrix"]
                logger.info('WLED matrix : ' + str(matrix["w"]) + 'x' + str(matrix["h"]))
            await wled.close()
        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error('An exception occurred: {}'.format(error))
            await wled.close()

        return matrix["w"], matrix["h"]

    @staticmethod
    async def put_wled_live(host, on: bool = True, live: bool = True, timeout: int = 2):
        """
        Put wled host on live mode if requested ( this should avoid wled take control )
        :param on:
        :param live:
        :param timeout:
        :param host:
        :return:
        """
        wled = WLED(host)
        try:
            wled.request_timeout = timeout
            await wled.connect()
            if wled.connected:
                if await wled.request(uri='/json', method='POST', data={'on': on, 'live': live}):
                    await wled.close()
                    return True
                else:
                    return False
            else:
                logger.warning(f"Not able to connect to WLED device: {host}")
                return False
        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f"Not able to set WLED device {host} in 'live' mode. Got this error : {error}")
            await wled.close()
            return False

    @staticmethod
    def active_window():
        """ Provide active window title """

        return pwc.getActiveWindow().title

    @staticmethod
    def windows_titles():
        """ Provide a list of all window titles by applications """

        return pwc.getAllAppsWindowsTitles()

    @staticmethod
    def dev_list_update():
        """
        Update Media device list depend on OS
        av is used to try to have cross-platform solution
        """
        CASTUtils.dev_list = []

        try:
            import av

            with av.logging.Capture(True) as logs:  # this will capture av output
                # av command depend on running OS
                if platform.system() == 'Windows':
                    av.open('dummy', 'r', format='dshow', options={'list_devices': 'True'})
                elif platform.system() == 'Darwin':
                    av.open('', 'r', format='avfoundation', options={'list_devices': 'True'})

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error('An exception occurred: {}'.format(error))

        devicenumber: int = 0
        typedev: str = ''

        # linux
        if platform.system() == 'Linux':
            from linuxpy.video import device as linux_dev

            dev = linux_dev.iter_devices()
            i = 0
            for item in dev:
                i += 1
                devname = str(item)
                typedev = 'VIDEO'
                devicenumber = i
                CASTUtils.dev_list.append((devname, typedev, devicenumber))

        else:
            # Win / darwin / others
            for i, name in enumerate(logs):
                if platform.system() == 'Windows':
                    if '"' in name[2] and 'Alternative' not in name[2]:
                        devname = name[2]
                        typedev = logs[i + 1][2].replace(" (", "")
                        CASTUtils.dev_list.append((devname, typedev, devicenumber))
                        devicenumber += 1

                elif platform.system() == 'Darwin':
                    if 'AVFoundation video device' in name:
                        typedev = 'video'
                    elif 'AVFoundation audio device' in name:
                        typedev = 'audio'
                    else:
                        numbers_in_brackets = re.findall(r'\[(\d+)\]', name)
                        if numbers_in_brackets:
                            devicenumber = int(numbers_in_brackets[0])

                        # Define the regular expression pattern to match
                        pattern = r"\[\d+\] (.*)"
                        # Use re.search() to find the first match
                        match = re.search(pattern, name)
                        if match:
                            # Extract the desired substring
                            devname = match.group(1)
                        else:
                            devname = "unknown"

                        CASTUtils.dev_list.append((devname, typedev, devicenumber))

                else:
                    logger.error(f"unsupported platform : {platform.system()}")
                    return False

        return True

    # resize image to specific width/height, optional ratio
    @staticmethod
    def resize_keep_aspect_ratio(image, target_width, target_height, ratio):

        if ratio:
            # First crop the image to the target aspect ratio
            aspect_ratio = image.shape[1] / image.shape[0]
            if target_height > 0:
                aspect_ratio = target_width / target_height
            image_aspect_ratio = image.shape[1] / image.shape[0]

            if image_aspect_ratio > aspect_ratio:
                # Crop the width
                new_width = int(image.shape[0] * aspect_ratio)
                start = (image.shape[1] - new_width) // 2
                image = image[:, start: start + new_width]
            else:
                # Crop the height
                new_height = int(image.shape[1] / aspect_ratio)
                start = (image.shape[0] - new_height) // 2
                image = image[start: start + new_height, :]

        # Resize to the target size
        image = cv2.resize(image, (target_width, target_height))
        return image

    @staticmethod
    def resize_image(image, target_width=None, target_height=None, interpolation=cv2.INTER_AREA, keep_ratio=True):
        """
        Resize the input image while maintaining the aspect ratio.

        Parameters:
        - image: Input image
        - width: Target width (optional)
        - height: Target height (optional)
        - interpolation: Interpolation method (default: cv2.INTER_AREA)
        - keep_ratio : preserve original ratio

        Returns:
        - Resized image
        """

        if keep_ratio:
            # Get the dimensions of the original image
            h, w = image.shape[:2]

            # Calculate aspect ratio
            aspect_ratio = w / h

            # If both width and height are None, return the original image
            if target_width is None and target_height is None:
                return image

            # If only width is provided, calculate height based on aspect ratio
            if target_width is not None and target_height is None:
                target_height = int(target_width / aspect_ratio)

            # If only height is provided, calculate width based on aspect ratio
            elif target_height is not None and target_width is None:
                target_width = int(target_height * aspect_ratio)

            # Resize image
            resized_image = cv2.resize(image, (target_width, target_height), interpolation=interpolation)

        else:
            # Resize image
            resized_image = cv2.resize(image, (target_width, target_height), interpolation=interpolation)

        return resized_image

    @staticmethod
    def pixelart_image(image_np, width_x, height_y):
        """ Convert image array to pixel art using cv """

        # Get input size
        orig_height, orig_width = image_np.shape[:2]
        # Desired "pixelated" size
        w, h = (width_x, height_y)

        # Resize input to "pixelated" size
        temp_img = cv2.resize(image_np, (w, h), interpolation=cv2.INTER_LINEAR)
        # Initialize output image
        pixelart_img = cv2.resize(temp_img, (orig_width, orig_height), interpolation=cv2.INTER_NEAREST)

        return pixelart_img

    @staticmethod
    def split_image_to_matrix(image_np, num_matrices_x, num_matrices_y):
        """
         Split the image (np array) into equal parts
         sub_images = split_image_to_matrix(image_np, num_matrices_x, num_matrices_y)
         Now you have a list of NumPy arrays, each containing a part of the image
         You can further process them as needed

         ---
         return n sub-images array
        """
        CASTUtils.matrix_x = num_matrices_x
        CASTUtils.matrix_y = num_matrices_y

        # Resize the image to ensure it's divisible into equal parts
        image_height, image_width = image_np.shape[:2]
        sub_image_width = image_width // num_matrices_x
        sub_image_height = image_height // num_matrices_y

        # Split the image into num_matrices_x * num_matrices_y parts
        sub_images = []
        for y in range(num_matrices_y):
            for x in range(num_matrices_x):
                sub_image = image_np[
                            y * sub_image_height: (y + 1) * sub_image_height,
                            x * sub_image_width: (x + 1) * sub_image_width]
                sub_images.append(sub_image)

        return sub_images

    # validate json received by ws
    @staticmethod
    def validate_ws_json_input(input_data):
        """
        Validate data received via WS comply to action/type/param/
            Some params are mandatory
        """

        if not isinstance(input_data, dict):
            logger.error('WEBSOCKET: need Json')
            return False

        if "action" not in input_data:
            logger.error('WEBSOCKET: action key is missing')
            return False

        action = input_data["action"]
        if not isinstance(action, dict):
            logger.error('WEBSOCKET: need Json')
            return False

        if "type" not in action or not isinstance(action["type"], str):
            logger.error('WEBSOCKET: need type str')
            return False

        if "param" not in action or not isinstance(action["param"], dict):
            logger.error('WEBSOCKET: param Json')
            return False

        # Define mandatory parameters and their expected types
        mandatory_params = {
            "image_number": int,
            "device_number": int,
            "class_name": str
        }

        # Check for mandatory parameters
        for param, param_type in mandatory_params.items():
            if param not in action["param"] or not isinstance(action["param"][param], param_type):
                logger.error('WEBSOCKET: mandatory params missing or type not adequate')
                return False

        return True

    @staticmethod
    def bytes2human(n):
        # http://code.activestate.com/recipes/578019
        # >>> bytes2human(10000)
        # '9.8K'
        # >>> bytes2human(100001221)
        # '95.4M'
        symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
        prefix = {}
        for i, s in enumerate(symbols):
            prefix[s] = 1 << (i + 1) * 10
        for s in reversed(symbols):
            if abs(n) >= prefix[s]:
                value = float(n) / prefix[s]
                return '%.1f%s' % (value, s)
        return "%sB" % n

    @staticmethod
    def validate_ip_address(ip_string):
        """ check if valid IP format """

        try:
            ipaddress.ip_address(ip_string)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_valid_cast_device(input_string):
        """
        Validate if cast device input is on this format [(0,'IP')]
        :param input_string:
        :return:
        """

        # Define a regex pattern to match the format [(number, 'IP'), ...]
        pattern = (r'\[\s*\(\s*\d+\s*,\s*\'(?:\d{1,3}\.){3}\d{1,3}\'\s*\)\s*(?:,\s*\(\s*\d+\s*,\s*\'(?:\d{1,'
                   r'3}\.){3}\d{1,3}\'\s*\)\s*)*\]')

        # Use the search function to check if the input string matches the pattern
        return re.search(pattern, input_string) is not None

    @staticmethod
    def check_ip_alive(ip_address, port=80, timeout=2):
        """
        efficiently check if an IP address is alive or not by testing connection on specified port
         e.g. WLED allow port 80
        """

        sock = None
        try:
            # Create a new socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set a timeout for the connection attempt
            sock.settimeout(timeout)
            # Attempt to connect to the IP address and port
            result = sock.connect_ex((ip_address, port))
            # Check if the connection was successful
            if result == 0:
                return True  # Host is reachable
            else:
                return False  # Host is not reachable
        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'Error on check IP : {error}')
            return False
        finally:
            # Close the socket
            sock.close()

    @staticmethod
    def check_and_clean_todo_list(class_name):
        """
        clean the to do list for a Class
        """
        logger.warning(f'Something wrong happened. To Do list has been cleared for {class_name}')
        class_name.cast_name.todo = []


class HTTPDiscovery:
    """
     zeroconf browse for network devices (http: this includes wled)
    """

    def __init__(self):
        self.http_devices: dict = {}
        self.duration: int = 5

    def add_service(self, zeroconf, ser_type, name):
        info = zeroconf.get_service_info(ser_type, name)
        name = name.replace('._http._tcp.local.', '')
        address = socket.inet_ntoa(info.addresses[0])
        port = info.port
        self.http_devices[name] = {"address": address, "port": port}

    def remove_service(self, name):
        if name in self.http_devices:
            del self.http_devices[name]

    def update_service(self, zeroconf, ser_type, name):
        pass

    def discover(self):
        zeroconf = Zeroconf()
        ServiceBrowser(zeroconf, "_http._tcp.local.", self)
        logger.info('Scanning network devices ...')
        time.sleep(self.duration)
        zeroconf.close()
        logger.info('Scanning network devices ... Done')


class LogElementHandler(logging.Handler):
    """ A logging handler that emits messages to a log element."""

    def __init__(self, element: ui.log, level: int = logging.NOTSET) -> None:
        self.element = element
        super().__init__(level)

    def emit(self, log_row: logging.LogRecord) -> None:
        try:
            msg = self.format(log_row)
            self.element.push(msg)
        except Exception:
            self.handleError(log_row)


class ImageUtils:

    @staticmethod
    def image_array_to_base64(nparray):
        # Convert NumPy array to PIL Image
        image = Image.fromarray(nparray)
        # Save the image to a bytes buffer
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        # Encode the bytes as Base64
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        # The img_str is the Base64 string representation of the image
        return img_str

    @staticmethod
    def process_raw_image(img: np.ndarray, filters: dict) -> np.ndarray:
        img = ImageUtils.apply_filters_cv2(img, filters)
        return img

    @staticmethod
    def apply_filters_cv2(img: np.ndarray, filters: dict) -> np.ndarray:
        # Convert to HSV for color adjustment
        if filters["saturation"] != 0:
            img = ImageUtils.filter_saturation(img, filters["saturation"])

        # Adjust brightness
        if filters["brightness"] != 0:
            img = ImageUtils.filter_brightness(img, filters["brightness"])

        # Adjust contrast
        if filters["contrast"] != 0:
            img = ImageUtils.filter_contrast(img, filters["contrast"])

        if filters["sharpen"] != 0:
            img = ImageUtils.filter_sharpen(img, filters["sharpen"])

        if filters["balance_r"] != 0 or filters["balance_g"] != 0 or filters['balance_b'] != 0:
            img = ImageUtils.filter_balance(
                img,
                {
                    "r": filters["balance_r"],
                    "g": filters["balance_g"],
                    "b": filters["balance_b"],
                },
            )

        return img

    @staticmethod
    def filter_balance(img, alpha):
        # scale the red, green, and blue channels
        scale = np.array([alpha["r"], alpha["g"], alpha["b"]])[np.newaxis, np.newaxis, :]

        img = (img * scale).astype(np.uint8)
        return img

    @staticmethod
    def filter_saturation(img, alpha):
        # Convert to HSV and split the channels
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)

        # Create a grayscale (desaturated) version
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        # Enhance color
        s_enhanced = cv2.addWeighted(s, alpha, gray, 1 - alpha, 0)

        # Merge and convert back to RGB
        enhanced_img = cv2.cvtColor(cv2.merge([h, s_enhanced, v]), cv2.COLOR_HSV2RGB)
        return enhanced_img

    @staticmethod
    def filter_brightness(img, alpha):
        # Create a black image
        black_img = np.zeros_like(img)

        # Enhance brightness
        enhanced_img = cv2.addWeighted(img, alpha, black_img, 1 - alpha, 0)
        return enhanced_img

    @staticmethod
    def filter_contrast(img, alpha):
        # Compute the mean luminance (gray level)
        mean_luminance = np.mean(img)

        # Create a gray image of mean luminance
        gray_img = np.full_like(img, mean_luminance)

        # Enhance contrast
        enhanced_img = cv2.addWeighted(img, alpha, gray_img, 1 - alpha, 0)
        return enhanced_img

    @staticmethod
    def filter_sharpen(img, alpha):
        kernel = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]]) * alpha
        kernel[1, 1] += 1
        img = cv2.filter2D(img, -1, kernel)
        return img

    @staticmethod
    def image_to_ascii(image):
        # Convert the image to ASCII art
        ascii_chars = "@%#*+=-:. "
        width, height = image.size
        image = image.resize((width, height // 2))  # Correct aspect ratio
        image = image.convert("L")  # Convert to grayscale
        pixels = image.getdata()
        ascii_str = ""
        for pixel_value in pixels:
            ascii_str += ascii_chars[
                pixel_value // 32
                ]  # Map the pixel value to ascii_chars
        ascii_str_len = len(ascii_str)
        ascii_img = ""
        for i in range(0, ascii_str_len, width):
            ascii_img += ascii_str[i: i + width] + "\n"
        return ascii_img

    @staticmethod
    def grid_on_image(image, cols, rows):

        if cols == 0 or rows == 0:
            logger.error('Rows / cols should not be zero')

        else:

            # Calculate cell size based on image dimensions and grid size
            cell_width = image.shape[1] // cols
            cell_height = image.shape[0] // rows

            # Calculate font size based on image size
            font_scale = min(image.shape[0], image.shape[1]) // 250
            if font_scale < .3:
                font_scale = .3

            # Draw the grid
            for i in range(1, rows):
                cv2.line(image, (0, i * cell_height), (image.shape[1], i * cell_height), (255, 255, 255), 2)
            for j in range(1, cols):
                cv2.line(image, (j * cell_width, 0), (j * cell_width, image.shape[0]), (255, 255, 255), 2)

            # Add numbers to the grid
            count = 0
            for i in range(rows):
                for j in range(cols):
                    # Calculate text position dynamically
                    text_x = j * cell_width + int(0.1 * cell_width)
                    text_y = i * cell_height + int(0.8 * cell_height)
                    cv2.putText(image, str(count), (text_x, text_y),
                                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 2)
                    count += 1

        return image


class NetGraph:
    timestamps = []
    mb_rec = []
    mb_sent = []
    last_rec = psutil.net_io_counters().bytes_recv
    last_sent = psutil.net_io_counters().bytes_sent

    @staticmethod
    def update_data(data):
        """
        Will update data from psutil
        # plt.xlabel('Time')
        # plt.ylabel('MB')
        # plt.title("Real-Time Bandwidth utilization")

        """
        # global last_rec, last_sent
        bytes_rec = psutil.net_io_counters().bytes_recv
        bytes_sent = psutil.net_io_counters().bytes_sent

        new_rec = (bytes_rec - NetGraph.last_rec) / 1024 / 1024
        new_sent = (bytes_sent - NetGraph.last_sent) / 1024 / 1024

        NetGraph.timestamps.append(time.time())
        NetGraph.mb_rec.append(new_rec)
        NetGraph.mb_sent.append(new_sent)

        if len(NetGraph.timestamps) > 600:
            NetGraph.timestamps.pop(0)
            NetGraph.mb_rec.pop(0)
            NetGraph.mb_sent.pop(0)

        NetGraph.ax.clear()
        NetGraph.ax.plot(NetGraph.timestamps, NetGraph.mb_rec, label='MB Received')
        NetGraph.ax.plot(NetGraph.timestamps, NetGraph.mb_sent, label='MB Sent')

        NetGraph.ax.legend()

        NetGraph.last_rec = bytes_rec
        NetGraph.last_sent = bytes_sent

    # Initialize the plot
    fig, ax = plt.subplots()
    fig.set_size_inches(5, 2)
    fig.suptitle('Network Utilization')
    anim = FuncAnimation(fig, update_data, interval=1000, cache_frame_data=False)
    # this one to avoid  UserWarning: Animation was deleted without rendering anything.
    anim._draw_was_started = True

    @staticmethod
    def run():
        plt.show()


class LocalFilePicker(ui.dialog):

    def __init__(self, directory: str, *,
                 upper_limit: Optional[str] = ..., multiple: bool = False, show_hidden_files: bool = False) -> None:
        """Local File Picker

        This is a simple file picker that allows you to select a file from the local filesystem where NiceGUI is running.

        :param directory: The directory to start in.
        :param upper_limit: The directory to stop at (None: no limit, default: same as the starting directory).
        :param multiple: Whether to allow multiple files to be selected.
        :param show_hidden_files: Whether to show hidden files.
        """
        super().__init__()

        self.drives_toggle = None
        self.path = Path(directory).expanduser()
        if upper_limit is None:
            self.upper_limit = None
        else:
            self.upper_limit = Path(directory if upper_limit == ... else upper_limit).expanduser()
        self.show_hidden_files = show_hidden_files

        with self, ui.card():
            self.add_drives_toggle()
            self.grid = ui.aggrid({
                'columnDefs': [{'field': 'name', 'headerName': 'File'}],
                'rowSelection': 'multiple' if multiple else 'single',
            }, html_columns=[0]).classes('w-96').on('cellDoubleClicked', self.handle_double_click)
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=self.close).props('outline')
                ui.button('Ok', on_click=self._handle_ok)
        self.update_grid()

    def add_drives_toggle(self):
        if platform.system() == 'Windows':
            import win32api
            drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
            self.drives_toggle = ui.toggle(drives, value=drives[0], on_change=self.update_drive)

    def update_drive(self):
        self.path = Path(self.drives_toggle.value).expanduser()
        self.update_grid()

    def update_grid(self) -> None:
        paths = list(self.path.glob('*'))
        if not self.show_hidden_files:
            paths = [p for p in paths if not p.name.startswith('.')]
        paths.sort(key=lambda p: p.name.lower())
        paths.sort(key=lambda p: not p.is_dir())

        self.grid.options['rowData'] = [
            {
                'name': f'📁 <strong>{p.name}</strong>' if p.is_dir() else p.name,
                'path': str(p),
            }
            for p in paths
        ]
        if self.upper_limit is None and self.path != self.path.parent or \
                self.upper_limit is not None and self.path != self.upper_limit:
            self.grid.options['rowData'].insert(0, {
                'name': '📁 <strong>..</strong>',
                'path': str(self.path.parent),
            })
        self.grid.update()

    def handle_double_click(self, e: events.GenericEventArguments) -> None:
        self.path = Path(e.args['data']['path'])
        if self.path.is_dir():
            self.update_grid()
        else:
            self.submit([str(self.path)])

    async def _handle_ok(self):
        rows = await ui.run_javascript(f'getElement({self.grid.id}).gridOptions.api.getSelectedRows()')
        self.submit([r['path'] for r in rows])
