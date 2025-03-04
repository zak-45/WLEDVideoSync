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
#
"""

import contextlib

from str2bool import str2bool
from pathlib import Path as PathLib

try:
    from yt_dlp import YoutubeDL
except Exception as e:
    print(f'INFO : this is Not a YT version: {e}')

import time
import shelve
import os
import sys
import inspect
import logging
import logging.config
import traceback
import json
import re
import platform
import multiprocessing
import subprocess
import configparser
import io
import pywinctl as pwc
import tkinter as tk
import socket
import ipaddress
import requests

import av
import numpy as np

from pytubefix import Search
from asyncio import create_task
from wled import WLED
from zeroconf import ServiceBrowser, Zeroconf
from nicegui import ui, run
from screeninfo import get_monitors
from PIL import Image
from coldtype.text.reader import Font
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger.utils')

class CASTUtils:
    """Provides utility functions for various CAST operations.

    This class offers a collection of static methods for tasks such as
    system font retrieval, media format conversion, logging setup,
    configuration management, network operations, and more.
    """
    dev_list: list = []
    matrix_x: int = 0
    matrix_y: int = 0
    yt_file_name: str = ''
    yt_file_size_bytes = 0
    yt_file_size_remain_bytes = 0

    ddp_devices: list = []  # all DDP device instances

    font_dict = {}
    font_dirs = []

    def __init__(self):
        pass


    @staticmethod
    def clean_tmp():
        cfg_mgr.logger.debug('Remove tmp files')
        try:

            # some cleaning
            cfg_mgr.logger.info('Cleaning ...')
            cfg_mgr.logger.debug('Remove tmp files')
            for tmp_filename in PathLib("tmp/").glob("*_file.*"):
                tmp_filename.unlink()

            # remove yt files
            if str2bool(cfg_mgr.app_config['keep_yt']) is not True:
                for media_filename in PathLib("media/").glob("yt-tmp-*.*"):
                    media_filename.unlink()

            # remove image files
            if str2bool(cfg_mgr.app_config['keep_image']) is not True:
                for img_filename in PathLib("media/").glob("image-tmp_*_*.jpg"):
                    img_filename.unlink()


        except Exception as error:
            cfg_mgr.logger.error(f'Error to remove tmp files : {error}')


    @staticmethod
    def get_queue_manager_settings():
        
        ip = '127.0.0.1'
        port = 50000
        with contextlib.suppress(Exception):
            if cfg_mgr.manager_config is not None:
                if cfg_mgr.manager_config['manager_ip'] != '':
                    ip = cfg_mgr.manager_config['manager_ip']
                if int(cfg_mgr.manager_config['manager_port']) != 0: 
                    port = int(cfg_mgr.manager_config['manager_port'])
                    
        return ip, port

    @staticmethod
    def attach_to_queue_manager():
        from src.utl.sharedlistclient import SharedListClient

        ip, port = CASTUtils.get_queue_manager_settings()
        return SharedListClient(sl_ip_address=ip, sl_port=port)

    @staticmethod
    def attach_to_manager_queue(queue_name):

        sl = None
        width = None
        height = None
        with contextlib.suppress(Exception):
            client =  CASTUtils.attach_to_queue_manager()
            if status := client.connect():
                sl = client.attach_to_shared_list(queue_name)
                sl_info = client.get_shared_list_info(queue_name)
                width = sl_info['w']
                height = sl_info['h']

        return sl, width, height

    @staticmethod
    def get_system_fonts():
        """Retrieve a dictionary of system fonts and a list of unique font directories.

        This function retrieves all available system fonts, returning them as a dictionary
        where keys are font stems and values are string representations of the font paths.
        It also returns a list of unique directories containing these fonts.

                - dict: A dictionary mapping font stems to font paths.
                - list: A list of unique font directories.
        """
        fonts = Font.List('')
        CASTUtils.font_dict = {font.stem: str(font) for font in fonts}
        CASTUtils.font_dirs = sorted(list({os.path.dirname(str(font)) for font in fonts}))  # Extract and deduplicate directories


    @staticmethod
    def mp4_to_gif(mp4_file, gif_file, loop: int = 0, duration: int = 100):
        """Convert an MP4 file to a GIF.

        Reads frames from an MP4 file using pyav, converts them to RGB numpy arrays,
        and then saves them as a GIF using Pillow.
        """
        # Open the MP4 file using pyav
        container = av.open(mp4_file)

        # Read the frames from the first video stream
        frames = []
        for frame in container.decode(video=0):
            # Convert the frame to numpy array (RGB format)
            img = frame.to_image()
            img = np.array(img)

            # Append the frame to the list
            frames.append(img)

        # Create a GIF from the frames
        frames_pil = [Image.fromarray(frame) for frame in frames]
        frames_pil[0].save(gif_file, save_all=True, append_images=frames_pil[1:], loop=loop, duration=duration)


    @staticmethod
    def update_ddp_list(cast_ip, ddp_obj):
        """Update the list of DDP devices.

        Adds a new DDP device object to the global list if it doesn't already exist.
        """
        ddp_exist = any(
            cast_ip == device._destination for device in CASTUtils.ddp_devices
        )
        if not ddp_exist:
            CASTUtils.ddp_devices.append(ddp_obj)

    @staticmethod
    def compile_info():
        """ read version info file """

        with open(cfg_mgr.app_root_path(f'assets/version-{sys.platform.lower()}.json'), 'r') as file:
            json_info = json.loads(file.read().replace("\\", "\\\\"))

        return json_info

    @staticmethod
    def update_ini_key(file_path, section, key, new_value):
        """
        Update an ini key

        """
        # Create a ConfigParser object
        config = configparser.ConfigParser()

        try:
            cfg_mgr.logger.debug(f'In update_ini_key , ini file : {file_path}')
        except (NameError, AttributeError):
            # this will be print only during init app as logger is not yet defined (NameError)
            print(f'In update_ini_key , ini file : {file_path}')

        config.read(file_path)

        # Check if the section exists
        if not config.has_section(section):
            raise ValueError(f"Section '{section}' not found in the INI file.")

        # Check if the key exists within the section
        if not config.has_option(section, key):
            raise ValueError(f"Key '{key}' not found in the section '{section}'.")

        # Update the key with the new value
        config.set(section, key, new_value)

        # Write the updated configuration back to the file
        with open(file_path, 'w') as configfile:
            config.write(configfile)

        try:
            cfg_mgr.logger.debug(f"INI Updated '{key}' to '{new_value}' in section '{section}'.")
        except (NameError, AttributeError):
            # this will be print only during init app as logger is not yet defined (NameError)
            print(f"INI Updated '{key}' to '{new_value}' in section '{section}'.")

    @staticmethod
    def mp_setup():
        """
        Set process action/type : fork, spawn ...
        Main test for platform
            macOS / linux need specific case
        """
        if sys.platform.lower() != 'linux':
            return multiprocessing.Process, multiprocessing.Queue # Direct return
        ctx = multiprocessing.get_context('spawn')
        return ctx.Process, ctx.Queue # Direct return

    @staticmethod
    def sl_clean(sl, sl_process, t_name):
        """ clean ShareableList """
        try:
            if sl is not None:
                # close the shared memory
                sl.shm.close()
                # destroy the shared memory
                sl.shm.unlink()
            if sl_process is not None:
                cfg_mgr.logger.debug(f'Stopping Child Process for Preview if any : {t_name}')
                sl_process.kill()
        except Exception as e:
            cfg_mgr.logger.error(f'Error on SL clean : {e}')

    @staticmethod
    def list_av_formats():
        """List available AV formats.

        Returns a sorted list of strings representing the available AV formats.
        """
        dict_formats = list(av.formats_available)
        return sorted(dict_formats)

    @staticmethod
    def list_av_codecs():
        """List available AV codecs.

        Returns a sorted list of strings representing the available AV codecs.
        """
        dict_codecs = list(av.codec.codecs_available)
        return sorted(dict_codecs)

    @staticmethod
    async def list_yt_formats(url):
        """ List available format for an YT Url """

        ydl_opts = {
            'listformats': True,
            'socket_timeout': 2,  # timeout try access Url
            'noplaylist': True,  # Do not download playlists
            'ignoreerrors': True,  # Ignore errors, such as unavailable formats
            'quiet': True,  # Suppress unnecessary output
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return info

    @staticmethod
    async def youtube_download(yt_url: str = None, interactive: bool = True, log_ui=None):
        """download video from YouTube"""

        # select from ini file
        download_format = cfg_mgr.custom_config['yt-format']

        def post_hook(d):
            if d['status'] == 'finished':
                final_filename = d.get('info_dict').get('_filename')
                CASTUtils.yt_file_name = final_filename
                CASTUtils.yt_file_size_remain_bytes = 0
                cfg_mgr.logger.debug(f"Finished Post Process {final_filename}")

        if interactive:
            if log_ui is not None:
                handler = LogElementHandler(log_ui)
                cfg_mgr.logger.addHandler(handler)
                ui.context.client.on_disconnect(lambda: cfg_mgr.logger.removeHandler(handler))

            def progress_hook(d):
                if d['status'] == 'downloading':
                    if 'total_bytes_estimate' in d:
                        CASTUtils.yt_file_size_bytes = d['total_bytes_estimate']
                        CASTUtils.yt_file_size_remain_bytes = d['total_bytes_estimate'] - d['downloaded_bytes']
                    if 'total_bytes' in d:
                        CASTUtils.yt_file_size_bytes = d['total_bytes']
                        CASTUtils.yt_file_size_remain_bytes = d['total_bytes'] - d['downloaded_bytes']

                    cfg_mgr.logger.debug(f"Downloading: {d['_percent_str']} of "
                                f"{d['_total_bytes_str']} at {d['_speed_str']} ETA {d['_eta_str']}")

                elif d['status'] == 'finished':
                    cfg_mgr.logger.debug(f"Finished downloading {d['filename']}")

            ydl_opts = {
                f'format': f'{download_format}',  # choose format to download
                'paths': {'temp': cfg_mgr.app_root_path('tmp')},  # temp folder
                'outtmpl': cfg_mgr.app_root_path('media/yt-tmp-%(title)s.%(ext)s'),  # Output file name format
                'progress_hooks': [progress_hook],  # Hook for progress
                'postprocessor_hooks': [post_hook],  # Hook for postprocessor
                'noplaylist': True,  # Do not download playlists
                'ignoreerrors': True,  # Ignore errors, such as unavailable formats
                'quiet': True,  # Suppress unnecessary output
            }

        else:

            ydl_opts = {
                # 'format': '134/18/best[height<=320][acodec!=none][vcodec!=none][ext=mp4]' single stream
                f'format': f'{download_format}',  # choose format to download
                'paths': {'temp': cfg_mgr.app_root_path('tmp')},  # temp folder
                'outtmpl': cfg_mgr.app_root_path('media/yt-tmp-%(title)s.%(ext)s'),  # Output file name format
                'postprocessor_hooks': [post_hook],  # Hook for postprocessor
                'noplaylist': True,  # Do not download playlists
                'ignoreerrors': True,  # Ignore errors, such as unavailable formats
                'quiet': True,  # Suppress unnecessary output
            }

        try:

            CASTUtils.yt_file_size_remain_bytes = 1024
            CASTUtils.yt_file_size_bytes = 1024

            ydl = YoutubeDL(ydl_opts)
            await run.io_bound(ydl.download, url_list=yt_url)

        except Exception as err:
            CASTUtils.yt_file_name = ''
            cfg_mgr.logger.error(f'Youtube error : {err}')

        return CASTUtils.yt_file_name

    @staticmethod
    def get_server_port():
        """ Retrieve server port number """

        server_port = 0
        try:
            # get pid
            p_pid = os.getpid()
            tmp_file = cfg_mgr.app_root_path(f"tmp/{p_pid}_file")
            # read file
            if os.path.isfile(f"{tmp_file}.dat"):
                infile = shelve.open(tmp_file)
                server_port = infile["server_port"]
        except Exception as er:
            server_port = 99

        return server_port

    @staticmethod
    async def get_wled_matrix_dimensions(host, timeout: int = 1):
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
                cfg_mgr.logger.debug(f'WLED matrix : {str(matrix["w"])} x {str(matrix["h"])}')
            await wled.close()
        except Exception as error:
            cfg_mgr.logger.error(traceback.format_exc())
            cfg_mgr.logger.error(f'An exception occurred: {error}')
            await wled.close()

        return matrix["w"], matrix["h"]

    @staticmethod
    def get_wled_info(host, timeout: int = 1):
        """
        Take wled information from WLED device
        :param host:
        :param timeout:
        :return:
        """
        try:
            url = f'http://{host}/json/info'
            result = requests.get(url, timeout=timeout)
            result = result.json()
        except Exception as error:
            cfg_mgr.logger.error(f'Not able to get WLED info : {error}')
            result = {}

        return result

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
                cfg_mgr.logger.warning(f"Not able to connect to WLED device: {host}")
                return False
        except Exception as error:
            cfg_mgr.logger.error(traceback.format_exc())
            cfg_mgr.logger.error(f"Not able to set WLED device {host} in 'live' mode. Got this error : {error}")
            await wled.close()
            return False

    @staticmethod
    def active_window():
        """ Provide active window title """

        return pwc.getActiveWindow().title

    @staticmethod
    def windows_titles():
        """ Provide a list of all window titles / hWnd by applications """

        try:
            # Assuming these are your custom classes
            class Point:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y

            class Size:
                def __init__(self, width, height):
                    self.width = width
                    self.height = height

            # Define a function to serialize custom objects
            def custom_serializer(obj):
                if isinstance(obj, Point):
                    return {"x": obj.x, "y": obj.y}
                elif isinstance(obj, Size):
                    return {"width": obj.width, "height": obj.height}
                raise TypeError(f"Type {type(obj)} not serializable")

            # Your dictionary
            data = pwc.getAllWindowsDict()
            # Convert dictionary to JSON
            windows_all = json.dumps(data, default=custom_serializer, ensure_ascii=False, indent=4)
            windows_by_app = json.loads(windows_all)

        except Exception as er:
            cfg_mgr.logger.error(f"Error retrieving windows: {er}")
            return {}

        return windows_by_app

    @staticmethod
    def dev_list_update():
        """
        Update Media device list depend on OS
        av is used to try to have cross-platform solution
        """
        CASTUtils.dev_list = []
        devicenumber: int = 0
        typedev: str = ''

        if platform.system().lower() == 'darwin':
            try:
                import av

                with av.logging.Capture(True) as logs:  # this will capture av output
                    av.open('', 'r', format='avfoundation', options={'list_devices': 'True'})

            except Exception as error:
                cfg_mgr.logger.error(traceback.format_exc())
                cfg_mgr.logger.error(f'An exception occurred: {error}')

        # linux
        if platform.system().lower() == 'linux':
            from linuxpy.video import device as linux_dev

            dev = linux_dev.iter_devices()
            typedev = 'VIDEO'
            CASTUtils.dev_list.extend(
                (str(item), typedev, i) for i, item in enumerate(dev, start=1)
            )

        elif platform.system().lower() == 'windows':
            from pygrabber.dshow_graph import FilterGraph

            graph = FilterGraph()
            devices = graph.get_input_devices()
            typedev = 'video'
            for item in devices:
                devname = item
                CASTUtils.dev_list.append((devname, typedev, devicenumber))
                devicenumber += 1

        else:
            # darwin / others
            for i, name in enumerate(logs):
                if platform.system().lower() == 'windows':
                    if '"' in name[2] and 'Alternative' not in name[2]:
                        devname = name[2]
                        typedev = logs[i + 1][2].replace(" (", "")
                        CASTUtils.dev_list.append((devname, typedev, devicenumber))
                        devicenumber += 1

                elif platform.system().lower() == 'darwin':
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
                    cfg_mgr.logger.error(f"unsupported platform : {platform.system()}")
                    return False

        return True

    # validate json received by ws
    @staticmethod
    def validate_ws_json_input(input_data):
        """
        Validate data received via WS comply to action/type/param/
            Some params are mandatory
        """

        if not isinstance(input_data, dict):
            cfg_mgr.logger.error('WEBSOCKET: input not valid format--> need dict')
            return False

        if "action" not in input_data:
            cfg_mgr.logger.error('WEBSOCKET: action key is missing')
            return False

        action = input_data["action"]
        if not isinstance(action, dict):
            cfg_mgr.logger.error('WEBSOCKET: input not valid format--> need dict')
            return False

        if "type" not in action or not isinstance(action["type"], str):
            cfg_mgr.logger.error('WEBSOCKET: need type str')
            return False

        if "param" not in action or not isinstance(action["param"], dict):
            cfg_mgr.logger.error('WEBSOCKET: missing "param" or wrong type')
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
        """
        Check if the given string is a valid IP address format or a reachable hostname.
        Args:
            ip_string (str): The IP address or hostname to validate.
        Returns:
            bool: True if the input is a valid IP address or a reachable hostname, False otherwise.
        """

        def is_valid_hostname(hostname):
            """Check if the string is a valid hostname."""
            if len(hostname) > 255:
                return False
            if hostname[-1] == ".":
                hostname = hostname[:-1]
            allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
            return all(allowed.match(x) for x in hostname.split("."))

        # Check if it's a valid IP address
        try:
            ipaddress.ip_address(ip_string)
            return True
        except ValueError:
            pass

        # Check if it's a valid hostname
        if is_valid_hostname(ip_string):
            try:
                # Check if hostname is reachable
                socket.gethostbyname(ip_string)
                return True
            except socket.gaierror:
                return False

        return False

    @staticmethod
    def check_ip_alive(ip_address, port=80, timeout=1, ping=False):
        """
        efficiently check if an IP address is alive or not by testing connection on specified port
         e.g. WLED allow port 80
         or
         by using the ping command
        """

        if ping:

            param = '-n' if platform.system().lower() == 'windows' else '-c'

            command = ['ping', param, '1', ip_address]
            try:
                subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=timeout)
                return True
            except subprocess.CalledProcessError:
                return False
            except subprocess.TimeoutExpired:
                return False

        else:

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
                cfg_mgr.logger.error(traceback.format_exc())
                cfg_mgr.logger.error(f'Error on check IP : {error}')
                return False
            finally:
                # Close the socket
                sock.close()

    @staticmethod
    def check_and_clean_todo_list(class_name):
        """
        clean the to do list for a Class
        """
        cfg_mgr.logger.warning(f'Something wrong happened. To Do list has been cleared for {class_name}')
        class_name.cast_name.todo = []


    @staticmethod
    async def download_image(download_path, url, file_name, timeout: int = 3):
        """ Download an image from an Url """

        try:
            image_content = requests.get(url, timeout=timeout).content
            image_file = io.BytesIO(image_content)
            image = Image.open(image_file)
            image = image.convert('RGB')
            file_path = f'{download_path}/{file_name}'

            if os.path.isfile(file_path):
                cfg_mgr.logger.error(f'Image already exist : {file_path}')
            else:
                with open(file_path, "wb") as f:
                    image.save(f, "JPEG")

                cfg_mgr.logger.debug(f'Image saved to : {file_path}')

            return True

        except Exception as err:
            cfg_mgr.logger.error(f'Error to save image from {url} :  {err}')

            return False

    @staticmethod
    async def is_image_url(url, timeout: int = 2):
        """ detect if url contains an image """

        try:
            response = requests.get(url, stream=True, timeout=timeout)
            content_type = response.headers.get('Content-Type')
            if content_type and content_type.startswith('image/'):
                return True
            return False
        except requests.RequestException as err:
            cfg_mgr.logger.error(f"Error checking URL: {err}")
            return False

    @staticmethod
    def func_info(module_name=None):
        """ provide functions infos defined into a module """

        func_with_params = []

        # get all functions inside module
        all_functions = inspect.getmembers(module_name, inspect.isfunction)
        # Get info from each function
        for func in all_functions:
            func_data = {
                "name": func[0],
                "async": inspect.iscoroutinefunction(func[1]),
                "params": str(inspect.signature(func[1])),
                "info": (func[1].__doc__ or "None")
            }

            func_with_params.append(func_data)

        # Convert the list of dictionaries to a JSON string
        json_output = json.dumps(func_with_params)
        return json.loads(json_output)


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
        cfg_mgr.logger.debug('Scanning network devices ...')
        time.sleep(self.duration)
        zeroconf.close()
        cfg_mgr.logger.debug('Scanning network devices ... Done')


class LogElementHandler(logging.Handler):
    """ A logging handler that emits messages to a log element."""

    def __init__(self, element: ui.log, level: int = logging.NOTSET) -> None:
        self.element = element
        super().__init__(level)
        # define format for the LogRecord
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # set format
        self.setFormatter(formatter)


    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.element.push(msg)
        except Exception:
            self.handleError(record)


class ScreenAreaSelection:
    """ Retrieve coordinates from selected monitor region """

    coordinates = []
    screen_coordinates = []
    monitors = []

    def __init__(self, tk_root, dk_monitor):
        self.root = tk_root
        self.monitor = dk_monitor

        # Set the geometry to match the selected monitor
        self.root.geometry(f"{self.monitor.width}x{self.monitor.height}+{self.monitor.x}+{self.monitor.y}")
        self.root.overrideredirect(True)  # Remove window decorations

        self.root.withdraw()  # Hide the window initially to avoid flicker

        self.canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Apply transparency and show window after short delay
        self.root.after(100, self.apply_transparency)

    def apply_transparency(self):
        self.root.wm_attributes('-alpha', 0.5)  # Set window transparency
        self.root.deiconify()  # Show the window

    def on_button_press(self, event):
        # Save mouse drag start position
        self.start_x = event.x
        self.start_y = event.y
        # Create rectangle if not yet exist
        if not self.rect:
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='blue', width=4)

    def on_mouse_drag(self, event):
        cur_x, cur_y = (event.x, event.y)
        # Expand rectangle as you drag the mouse
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        # Get the coordinates of the rectangle
        coordinates = self.canvas.coords(self.rect)
        ScreenAreaSelection.coordinates = coordinates

        # Adjust coordinates to be relative to the screen
        screen_coordinates = [
            coordinates[0] + self.monitor.x,
            coordinates[1] + self.monitor.y,
            coordinates[2] + self.monitor.x,
            coordinates[3] + self.monitor.y,
        ]

        ScreenAreaSelection.screen_coordinates = screen_coordinates

        self.root.destroy()

    @staticmethod
    def run(monitor_number: int = 0):
        """
        Initiate tk-inter
        param : monitor number to draw selection
        """
        # get all monitors info
        monitors = get_monitors()
        ScreenAreaSelection.monitors = monitors
        """
        for i, m in enumerate(monitors):
            print(f"Monitor {i}: {m}")
        """
        # Change the monitor index as needed
        monitor_index = monitor_number  # Change this to the desired monitor index (0 for first , 1 for second, etc.)
        if monitor_index >= len(monitors):
            cfg_mgr.logger.warning(f"Monitor index {monitor_index} is out of range. Using the first monitor instead.")
            monitor_index = 0
        # monitor obj
        monitor = monitors[monitor_index]
        #
        root = tk.Tk()
        root.title("Area Selection on Monitor")
        ScreenAreaSelection(root, monitor)
        root.mainloop()


class YtSearch:
    """
    Search YT Video from input
    Display thumb and YT Plyer
    On click, copy YT Url to clipboard
    """

    def __init__(self, anime: bool = False):
        self.yt_search = None
        self.yt_anime = anime
        self.videos_search = None
        self.limit = 5
        ui.separator()
        with ui.row():
            self.my_search = ui.input('YT search')
            self.search_button = ui.button('search', icon='restore_page', color='blue') \
                .tooltip('Click to Validate')
            self.search_button.on_click(lambda: self.search_youtube())
            self.next_button = ui.button('More', on_click=lambda: self.next_search())
            self.next_button.set_visibility(False)
            self.number_found = ui.label('Result : ')

        self.search_result = ui.card()
        with self.search_result:
            ui.label('Search could take some time ....').classes('animate-pulse')

        self.yt_player = ui.page_sticky()

    def youtube_player(self, yt_id):
        """ YT Player in iframe """

        self.yt_player.clear()
        with self.yt_player:
            player = ui.card()
            if self.yt_anime:
                player.classes(add='animate__animated animate__slideInRight')
            youtube_url = f"https://www.youtube.com/embed/{yt_id}"
            with player:
                ui.html('<iframe width="350" height="230" '
                        f'src="{youtube_url}" '
                        'title="YouTube video player" '
                        'frameborder="0" '
                        'allow="autoplay;clipboard-write;encrypted-media;picture-in-picture" '
                        'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen>'
                        '</iframe>')

    async def search_youtube(self):
        """ Run Search YT from input """

        async def run_search():
            await create_task(self.py_search(self.my_search.value))

        self.search_button.props('loading')
        self.search_result.clear()
        ui.timer(.5, run_search, once=True)

    async def py_search(self, data):
        """ Search for YT from input """

        self.videos_search = Search(data)
        self.yt_search = self.videos_search.videos

        # number found
        number = len(self.yt_search)
        self.number_found.text = f'Number found: {number}'
        # activate 'more' button
        if number > 0:
            self.next_button.set_visibility(True)
            # re-create  result page
            await self.create_yt_page()
        else:
            self.number_found.text = 'Nothing Found'

        self.search_button.props(remove='loading')

    async def next_search(self):
        """ Next if you want more """

        self.limit += 5
        # await ui.context.client.connected()
        self.search_button.props('loading')
        await run.io_bound(self.videos_search.get_next_results)
        self.yt_search = self.videos_search.videos
        self.number_found.text = f'Number found: {len(self.yt_search)}'
        await self.create_yt_page()
        self.search_button.props(remove='loading')

    async def create_yt_page(self):
        """ Create YT search result """

        # clear as we recreate
        self.search_result.clear()
        # create
        with self.search_result.classes('w-full self-center'):
            for i in range(len(self.yt_search)):
                ui.separator()
                ui.label(self.yt_search[i].title)
                with ui.row(wrap=False).classes('w-1/2'):
                    yt_image = ui.image(self.yt_search[i].thumbnail_url).style(add='width: 150px;')
                    yt_image.on('mouseenter', lambda yt_str=self.yt_search[i]: self.youtube_player(yt_str.video_id))
                    with ui.column():
                        ui.label(f'Length: {self.yt_search[i].length}')
                        yt_url = ui.label(self.yt_search[i].watch_url)
                        yt_url.tooltip('Click to copy')
                        yt_url.style('text-decoration: underline; cursor: pointer;')
                        yt_url.on('click', lambda my_yt=yt_url: (ui.clipboard.write(my_yt.text),
                                                                 ui.notify('YT Url copied')))
                        with ui.row():
                            yt_watch_close = ui.icon('videocam_off', size='sm')
                            yt_watch_close.tooltip('Player OFF')
                            yt_watch_close.style('cursor: pointer')
                            yt_watch_close.on('click', lambda: self.yt_player.clear())
                            yt_watch = ui.icon('smart_display', size='sm')
                            yt_watch.tooltip('Player On')
                            yt_watch.style('cursor: pointer')
                            yt_watch.on('click', lambda yt_str=self.yt_search[i]: self.youtube_player(yt_str.video_id))

"""
Animate css class
"""

class AnimatedElement:
    """
    Add animation to UI Element, in / out
        In for create element
        Out for delete element
    Following is necessary as it's based on Animate.css
    # Add Animate.css to the HTML head
    ui.add_head_html(""
    <link rel="stylesheet" href="assets/css/animate.min.css"/>
    "")
    app.add_static_files('/assets', 'assets')
    Param:
        element_type : nicegui element e.g. card, label, ...
        animation_name : see https://animate.style/
        duration : custom animation delay
    """

    def __init__(self, element_type:type[any], animation_name_in='fadeIn', animation_name_out='fadeOut', duration=1.5):
        self.element_type = element_type
        self.animation_name_in = animation_name_in
        self.animation_name_out = animation_name_out
        self.duration = duration

    def generate_animation_classes(self, animation_name):
        # Generate the animation and duration classes
        animation_class = f'animate__{animation_name}'
        duration_class = f'custom-duration-{self.duration}s'
        return animation_class, duration_class

    def add_custom_css(self):
        # Add custom CSS for animation duration
        custom_css = f"""
        <style>
        .custom-duration-{self.duration}s {{
          animation-duration: {self.duration}s;
        }}
        </style>
        """
        ui.add_head_html(custom_css)

    def create_element(self, *args, **kwargs):
        """ Add class for in """
        self.add_custom_css()
        animation_class, duration_class = self.generate_animation_classes(self.animation_name_in)
        element = self.element_type(*args, **kwargs)
        element.classes(f'animate__animated {animation_class} {duration_class}')
        return element

    def delete_element(self, element):
        """ Add class for out and delete """
        animation_class, duration_class = self.generate_animation_classes(self.animation_name_out)
        element.classes(f'animate__animated {animation_class} {duration_class}')
        # Delay the actual deletion to allow the animation to complete
        ui.timer(self.duration, lambda: element.delete(), once=True)

