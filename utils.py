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
from youtubesearchpython.__future__ import VideosSearch
from yt_dlp import YoutubeDL

import asyncio

import logging
import logging.config
import concurrent_log_handler
import traceback

import re
import platform
import pywinctl as pwc
from wled import WLED

import time
import shelve
import os
import sys

from zeroconf import ServiceBrowser, Zeroconf
import socket
import ipaddress
import requests

from pathlib import Path
from typing import Optional

from nicegui import events, ui, run

import tkinter as tk
from screeninfo import get_monitors

import cfg_load as cfg
from str2bool import str2bool

import multiprocessing
import configparser


class CASTUtils:
    dev_list: list = []
    matrix_x: int = 0
    matrix_y: int = 0
    yt_file_name: str = ''
    yt_file_size_bytes = 0
    yt_file_size_remain_bytes = 0

    def __init__(self):
        pass

    @staticmethod
    def update_ini_key(file_path, section, key, new_value):
        # Create a ConfigParser object
        config = configparser.ConfigParser()

        # Read the existing INI file
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
            logger.info(f"Updated '{key}' to '{new_value}' in section '{section}'.")
        except NameError:
            print(f"Updated '{key}' to '{new_value}' in section '{section}'.")

    @staticmethod
    def mp_setup():
        """
        Main test for platform
            macOS / linux need specific case
        """
        if sys.platform.lower() == 'darwin' or sys.platform.lower() == 'linux':
            ctx = multiprocessing.get_context('spawn')
            process = ctx.Process
            queue = ctx.Queue
        else:
            process = multiprocessing.Process
            queue = multiprocessing.Queue

        return process, queue

    @staticmethod
    def sl_clean(sl, sl_process, t_name):
        """ clean ShareableList """

        if sl_process is not None:
            logger.info(f'Stopping Child Process for Preview if any : {t_name}')
            sl_process.kill()
        if sl is not None:
            # close the shared memory
            sl.shm.close()
            # destroy the shared memory
            sl.shm.unlink()

    @staticmethod
    def list_av_formats():
        import av
        dict_formats = []
        j = 0
        for item in av.formats_available:
            dict_formats.append(item)
            j += 1
        dict_formats = sorted(dict_formats)
        return dict_formats

    @staticmethod
    def list_av_codecs():
        import av
        dict_codecs = []
        j = 0
        for item in av.codec.codecs_available:
            dict_codecs.append(item)
            j += 1
        dict_codecs = sorted(dict_codecs)
        return dict_codecs

    @staticmethod
    async def list_yt_formats(url):
        """ List available format for an YT Url """

        ydl_opts = {
            'listformats': True,
            'noplaylist': True,  # Do not download playlists
            'ignoreerrors': True,  # Ignore errors, such as unavailable formats
            'quiet': True,  # Suppress unnecessary output
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return info

    @staticmethod
    async def youtube_download(yt_url: str = None, interactive: bool = True, log_ui=None):
        """download video from youtube"""

        # select from ini file
        config_data = CASTUtils.read_config()
        download_format = config_data[3]['yt-format']

        def post_hook(d):
            if d['status'] == 'finished':
                final_filename = d.get('info_dict').get('_filename')
                CASTUtils.yt_file_name = final_filename
                CASTUtils.yt_file_size_remain_bytes = 0
                logger.info(f"Finished Post Process {final_filename}")

        if interactive:
            if log_ui is not None:
                logger.addHandler(LogElementHandler(log_ui))

            def progress_hook(d):
                if d['status'] == 'downloading':
                    if 'total_bytes_estimate' in d:
                        CASTUtils.yt_file_size_bytes = d['total_bytes_estimate']
                        CASTUtils.yt_file_size_remain_bytes = d['total_bytes_estimate'] - d['downloaded_bytes']
                    if 'total_bytes' in d:
                        CASTUtils.yt_file_size_bytes = d['total_bytes']
                        CASTUtils.yt_file_size_remain_bytes = d['total_bytes'] - d['downloaded_bytes']

                    logger.info(f"Downloading: {d['_percent_str']} of "
                                f"{d['_total_bytes_str']} at {d['_speed_str']} ETA {d['_eta_str']}")

                elif d['status'] == 'finished':
                    logger.info(f"Finished downloading {d['filename']}")

            ydl_opts = {
                f'format': f'{download_format}',  # choose format to download
                'paths': {'temp': './tmp'},  # temp folder
                'outtmpl': './media/yt-tmp-%(title)s.%(ext)s',  # Output file name format
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
                'paths': {'temp': './tmp'},  # temp folder
                'outtmpl': './media/yt-tmp-%(title)s.%(ext)s',  # Output file name format
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

        except Exception as error:
            CASTUtils.yt_file_name = ''
            logger.info(f'Youtube error : {error}')

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
                logger.info(f'WLED matrix : {str(matrix["w"])} x {str(matrix["h"])}')
            await wled.close()
        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'An exception occurred: {error}')
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
            logger.error(f'Not able to get WLED info : {error}')
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
        devicenumber: int = 0
        typedev: str = ''

        if platform.system().lower() == 'darwin':
            try:
                import av

                with av.logging.Capture(True) as logs:  # this will capture av output
                    av.open('', 'r', format='avfoundation', options={'list_devices': 'True'})

            except Exception as error:
                logger.error(traceback.format_exc())
                logger.error(f'An exception occurred: {error}')

        # linux
        if platform.system().lower() == 'linux':
            from linuxpy.video import device as linux_dev

            dev = linux_dev.iter_devices()
            i = 0
            for item in dev:
                i += 1
                devname = str(item)
                typedev = 'VIDEO'
                devicenumber = i
                CASTUtils.dev_list.append((devname, typedev, devicenumber))

        elif platform.system().lower() == 'windows':
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            devices = graph.get_input_devices()
            for item in devices:
                devname = item
                typedev = 'video'
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
                    logger.error(f"unsupported platform : {platform.system()}")
                    return False

        return True

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

    @staticmethod
    def setup_logging(config_path='logging_config.ini', handler_name: str = None):
        if os.path.exists(config_path):
            logging.config.fileConfig(config_path, disable_existing_loggers=False)
            # trick: use the same name for all modules, ui.log will receive message from alls
            config_data = CASTUtils.read_config()
            if str2bool(config_data[1]['log_to_main']):
                v_logger = logging.getLogger('WLEDLogger')
            else:
                v_logger = logging.getLogger(handler_name)
            v_logger.info(f"Logging configured using {config_path} for {handler_name}")
        else:
            logging.basicConfig(level=logging.INFO)
            v_logger = logging.getLogger(handler_name)
            v_logger.warning(f"Logging config file {config_path} not found. Using basic configuration.")

        return v_logger

    @staticmethod
    def read_config():
        # load config file
        cast_config = cfg.load('config/WLEDVideoSync.ini')
        # config keys
        server_config = cast_config.get('server')
        app_config = cast_config.get('app')
        colors_config = cast_config.get('colors')
        custom_config = cast_config.get('custom')
        preset_config = cast_config.get('presets')

        return server_config, app_config, colors_config, custom_config, preset_config


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
        super().__init__(level)
        self.element = element
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
        if platform.system().lower() == 'windows':
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
        self.root.wm_attributes('-alpha', 0.5)  # Set window transparency
        self.root.configure()

        self.canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

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
            logger.info(f"Monitor index {monitor_index} is out of range. Using the first monitor instead.")
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
        self.yt_stream = None
        self.yt_search = None
        self.yt_anime = anime
        self.videos_search = None
        ui.separator()
        with ui.row():
            self.my_search = ui.input('YT search')
            self.search_button = ui.button('search', icon='restore_page', color='blue') \
                .tooltip('Click to Validate')
            self.search_button.on_click(lambda: self.search_youtube())
            self.next_button = ui.button('More', on_click=lambda: self.next_search())
            self.next_button.set_visibility(False)
            self.number_found = ui.label(f'Result : ')

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

        def run_search():
            asyncio.create_task(self.py_search(self.my_search.value))

        # await ui.context.client.connected()

        self.search_button.props('loading')
        self.search_result.clear()
        ui.timer(.5, run_search, once=True)

    async def py_search(self, data):
        """ Search for YT from input """

        self.videos_search = VideosSearch(data, limit=5)
        self.yt_search = await self.videos_search.next()

        # number found
        number = len(self.yt_search['result'])
        self.number_found.text = f'Number found: {number}'
        # activate 'more' button
        if number > 0:
            self.next_button.set_visibility(True)
            # re create  result page
            await self.create_yt_page(self.yt_search)
        else:
            self.number_found.text = 'Nothing Found'

        self.search_button.props(remove='loading')

    async def next_search(self):
        """ Next if you want more """

        # await ui.context.client.connected()
        self.search_button.props('loading')
        tmp_dict = await self.videos_search.next()
        if len(tmp_dict['result']) > 0:
            # search additional data
            self.yt_search.update(tmp_dict)
            # update number
            self.number_found.text = f'Number found: {len(tmp_dict["result"])}'
            # re create  result page
            await self.create_yt_page(self.yt_search)
        else:
            ui.notify('No more to search', position='center', type='negative', close_button=True)

        self.search_button.props(remove='loading')

    async def create_yt_page(self, data):
        """ Create YT search result """

        # clear as we recreate
        self.search_result.clear()
        # create
        with self.search_result.classes('w-full self-center'):
            for self.yt_stream in data['result']:
                ui.separator()
                ui.label(self.yt_stream['title'])
                with ui.row(wrap=False).classes('w-1/2'):
                    yt_image = ui.image(self.yt_stream['thumbnails'][0]['url']).classes('self-center w-1/2')
                    yt_image.on('mouseenter', lambda yt_str=self.yt_stream: self.youtube_player(yt_str['id']))
                    with ui.column():
                        ui.label(f'Length: {self.yt_stream["duration"]}')
                        yt_url = ui.label(self.yt_stream['link'])
                        yt_url.tooltip('Click to copy')
                        yt_url.style('text-decoration: underline; cursor: pointer;')
                        yt_url.on('click', lambda my_yt=yt_url: (ui.clipboard.write(my_yt.text),
                                                                 ui.notify('copied')))
                        with ui.row():
                            yt_watch_close = ui.icon('videocam_off', size='sm')
                            yt_watch_close.tooltip('Player OFF')
                            yt_watch_close.style('cursor: pointer')
                            yt_watch_close.on('click', lambda: self.yt_player.clear())
                            yt_watch = ui.icon('smart_display', size='sm')
                            yt_watch.tooltip('Player On')
                            yt_watch.style('cursor: pointer')
                            yt_watch.on('click', lambda yt_str=self.yt_stream: self.youtube_player(yt_str['id']))


class AnimatedElement:
    """
    Add animation to UI Element, in / out
        In for create element
        Out for delete element
    Following is necessary as its based on Animate.css
    # Add Animate.css to the HTML head
    ui.add_head_html(""
    <link rel="stylesheet" href="./assets/css/animate.min.css"/>
    "")
    app.add_static_files('/assets', 'assets')
    Param:
        element_type : nicegui element e.g. card, label, ...
        animation_name : see https://animate.style/
        duration : custom animation delay
    """

    def __init__(self, element_type, animation_name_in='fadeIn', animation_name_out='fadeOut', duration=1.5):
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


"""
When this env var exist, this mean run from the one-file compressed executable.
Load of the config is not possible, folder config should not exist.
This avoid FileNotFoundError.
This env not exist when run from the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    # read config
    # create logger
    logger = CASTUtils.setup_logging('config/logging.ini', 'WLEDLogger.utils')
