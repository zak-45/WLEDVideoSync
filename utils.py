# a: zak-45
# d: 13/03/2024
# v: 1.0.0
#
# CASTUtils
#
#          CAST utilities
#
# pywinctl provide a cross-platform window mgt.
# 
import logging
import logging.config
import traceback

import re
import av
import platform
import cv2
import pywinctl as pwc
from wled import WLED

import time

from zeroconf import ServiceBrowser, Zeroconf
import socket
import ipaddress

from nicegui import ui

# read config
logging.config.fileConfig('config/logging.ini')
# create logger
logger = logging.getLogger('WLEDLogger.utils')


class CASTUtils:
    dev_list: list = []
    matrix_x: int = 0
    matrix_y: int = 0

    def __init__(self):
        pass

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
            matrix = {"w": 1, "h": 1}

        return matrix["w"], matrix["h"]

    @staticmethod
    async def put_wled_live(host, on: bool = True, live: bool = True, timeout: int = 2):
        """
        Put wled host(s) on live mode if requested ( this should avoid wled take control )
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
            with av.logging.Capture(True) as logs:  # this will capture av output
                # av command depend on running OS
                if platform.system() == 'Windows':
                    av.open('dummy', 'r', format='dshow', options={'list_devices': 'True'})
                elif platform.system() == 'Linux':
                    av.open('', 'r', format='v4l2', options={'list_devices': 'True'})
                elif platform.system() == 'Darwin':
                    av.open('', 'r', format='avfoundation', options={'list_devices': 'True'})
        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error('An exception occurred: {}'.format(error))

        devicenumber: int = 0
        typedev: str = ''

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

            elif platform.system() == 'Linux':
                devname = name[0]
                CASTUtils.dev_list.append((devname, None, None))

            else:
                print(f"unsupported platform : {platform.system()}")
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
        temp = cv2.resize(image_np, (w, h), interpolation=cv2.INTER_LINEAR)
        # Initialize output image
        pixelart_img = cv2.resize(temp, (orig_width, orig_height), interpolation=cv2.INTER_NEAREST)

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

    # preview image of np array
    @staticmethod
    def preview(winname, np_image):
        cv2.imshow(winname, np_image)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.destroyAllWindows()

    # kill all preview image
    @staticmethod
    def preview_kill():
        cv2.destroyAllWindows()

    # validate json received by ws
    @staticmethod
    def validate_ws_json_input(input_data):
        """
        Validate data received via WS comply to action/type/param/
            Some params are mandatory
        """

        if not isinstance(input_data, dict):
            return False

        if "action" not in input_data:
            return False

        action = input_data["action"]
        if not isinstance(action, dict):
            return False

        if "type" not in action or not isinstance(action["type"], str):
            return False

        if "param" not in action or not isinstance(action["param"], dict):
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
                return False

        return True

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
    def check_ip_alive(ip_address, port=80, timeout=5):
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
        # 'class_name.cast_name.to do' = []


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
