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
Overview
This file, utils.py, provides a comprehensive utility class (CASTUtils) and supporting functions for
the WLEDVideoSync project. Its primary purpose is to centralize a wide range of helper methods and static utilities
that support media processing, device management, configuration, networking, and integration with WLED devices and YouTube.
The utilities are designed to be cross-platform, supporting Windows, macOS, and Linux, and facilitate operations such
as video and GIF manipulation, device discovery, API communication, configuration management, and more.

The file is a foundational component in the system, acting as a toolkit for higher-level application logic, especially
for tasks involving media conversion, device interaction, and network communication.

Key Components
1. CASTUtils Class
A static utility class containing a large collection of methods and attributes, including:

Media Processing Utilities: Methods for resizing videos and GIFs, converting videos to GIFs, extracting video dimensions,
    and listing available AV formats and codecs.
WLED Device Integration: Functions to upload GIFs to WLED devices, retrieve device info, set live mode, and get
    matrix dimensions.
YouTube Integration: Methods for downloading YouTube videos, listing available formats, and extracting direct video URLs
    using yt_dlp.
Configuration and File Management: Methods for updating INI files, cleaning temporary files, extracting filenames,
    and reading version info.
Device and Network Management: Functions to list video devices, validate IP addresses, check if an IP is alive,
    and manage shared queues for multiprocessing.
API and WebSocket Utilities: Async methods for making API requests and validating WebSocket JSON input.
System Font Management: Methods to retrieve system fonts and font directories.
Miscellaneous Utilities: Human-readable byte conversion, downloading and validating images, and introspection
    of module functions.

2. Logging and Configuration
Uses a centralized logger (utils_logger) for consistent logging across all utilities.
Integrates with a configuration manager (cfg_mgr) to access application settings and paths.

3. Cross-Platform Support
Handles platform-specific logic for device enumeration and multiprocessing setup, ensuring compatibility across
Windows, macOS, and Linux.

4. External Integrations
WLED: Communicates with WLED devices for LED matrix control and media uploads.
YouTube (yt_dlp): Downloads and processes YouTube videos.
Media Libraries: Uses av, cv2, and PIL for media manipulation.
Networking: Utilizes aiohttp, requests, and socket for HTTP and network operations.

5. Error Handling and Robustness
Extensive use of try/except blocks and context managers to handle errors gracefully and log issues for debugging.


"""
import asyncio
import contextlib
import urllib.parse
import shelve
import os
import sys
import inspect
import traceback
import json
import re
import subprocess
import configparser
import io
import socket
import ipaddress
import requests
import aiohttp
import av
import cv2
import numpy as np

try:
    from yt_dlp import YoutubeDL as YTdl
except Exception as e:
    print(f'INFO : this is Not a YT version: {e}')

from threading import Lock
from str2bool import str2bool
from pathlib import Path as PathLib
from cv2_enumerate_cameras import enumerate_cameras
from wled import WLED
from nicegui import run
from PIL import Image
from unidecode import unidecode
from coldtype.text.reader import Font
from wled.exceptions import WLEDConnectionError, WLEDError # Specific WLED errors
from ping3 import ping as wled_ping

from src.gui.tkarea import ScreenAreaSelection as SCArea

from configmanager import cfg_mgr, PLATFORM, WLED_PID_TMP_FILE, LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.utils')
utils_logger = logger_manager.logger


class LatestFrame:
    """A thread-safe class to hold the latest frame from a cast."""

    def __init__(self):
        self.frame = None
        self.lock = Lock()

    def set(self, frame):
        """Safely sets the latest frame."""
        with self.lock:
            self.frame = frame

    def get(self):
        """Safely gets the latest frame."""
        with self.lock:
            return self.frame


class CastAPI:
    """
    Provides a global namespace for sharing UI-related state across the WLEDVideoSync application.

    This class holds variables and references needed by different UI components and pages, such as timers, preview frames,
    and shared configuration. It is used to coordinate state and actions throughout the application's lifecycle.
    """

    dark_mode = False
    netstat_process = None
    charts_row = None
    player = None
    video_fps = 0
    video_frames = 0
    current_frame = 0
    progress_bar = None
    cpu_chart = None
    video_slider = None
    media_button_sync = None
    slider_button_sync = None
    type_sync = 'none'  # none, slider , player
    last_type_sync = ''  # slider , player
    search_areas = []  # contains YT search
    media_cast = None
    media_cast_run = None
    desktop_cast = None
    desktop_cast_run = None
    total_frames = 0
    total_packets = 0
    ram = 0
    cpu = 0
    w_image = None
    windows_titles = {}
    new_viinput_value = ''
    root_timer = None
    player_timer = None
    info_timer = None
    control_panel = None
    loop = None
    previews = {}  # Thread-safe dictionary to hold latest preview frames

    def __init__(self):
        pass



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
    async def run_mobile_cast(file, dark):
        """
        Launches the mobile camera server in a separate, isolated process.

        This is the recommended way to run a secondary service from a compiled Nuitka
        executable. It re-launches the main executable (`sys.executable`) with a special
        command-line flag (`--run-mobile-server`) that tells it to start the mobile
        server instead of the main GUI.
        """

        executable_path = sys.executable  # This correctly points to the running executable

        try:
            utils_logger.info(f"Launching mobile server via subprocess: {executable_path} --run-mobile-server")

            # Use Popen for a non-blocking call to start the server process
            if CASTUtils.is_compiled():
                subprocess.Popen([executable_path,
                                  '--run-mobile-server',
                                  '--file', file,
                                  '--dark', dark])
            else:
                subprocess.Popen([executable_path,
                                  f'{cfg_mgr.app_root_path("WLEDVideoSync.py")}',
                                  '--run-mobile-server',
                                  '--file', file,
                                  '--dark', dark])

            utils_logger.info("Mobile server process started.")
        except Exception as er:
            utils_logger.error(f'Error launching mobile server subprocess: {er}', exc_info=True)

    @staticmethod
    async def run_sys_charts(file, dark:bool = False, params: list = None):
        """
        Launches the system charts server in a separate, isolated process.

        This is the recommended way to run a secondary service from a compiled Nuitka
        executable. It re-launches the main executable (`sys.executable`) with a special
        command-line flag (`--run-sys-charts`) that tells it to start the system charts
        server instead of the main GUI.

        Args:
            file (str) : absolute path for inter process file
            dark (bool) : dark mode
            params (list, optional): A list of additional command-line arguments to pass
                                      to the runcharts.py script (e.g., ['--sysstats']).

        """

        executable_path = sys.executable  # This correctly points to the running executable
        dev_list = await CASTUtils.get_all_running_hosts(file)

        # Start with the base command and essential arguments
        command = ['--run-sys-charts', '--file', file, '--dev_list', ','.join(dev_list)]

        # Add boolean flags if they are true
        if dark:
            command.append('--dark')
        if str2bool(cfg_mgr.app_config['native_ui']):
            command.append('--native')

        # Append any extra user-provided parameters
        if params:
            command.extend(params)

        try:
            utils_logger.info(f"Launching sysstat server via subprocess: {executable_path} {command}")

            # Use Popen for a non-blocking call to start the server process
            if CASTUtils.is_compiled():
                subprocess.Popen([executable_path,*command])
            else:
                subprocess.Popen([executable_path,
                                  f'{cfg_mgr.app_root_path("WLEDVideoSync.py")}',
                                  *command])

            utils_logger.info("System charts server process started.")

        except Exception as er:
            utils_logger.error(f'Error launching sysstat server subprocess: {er}', exc_info=True)

    @staticmethod
    def get_local_ip_address(remote_server="192.0.2.1"):
        """Returns the local IP address

        Determines the local network interface IP address by connecting to a remote server using a UDP socket.

        This function's purpose is to discover the primary local IP address of the computer it's running on.
        This is the IP address that other devices on the same local network (like a mobile phone scanning a QR code)
        need to use to connect back to this application.

        Args:
            remote_server (str): The IP address of the remote server to connect to. Defaults to "192.0.2.1".

        Returns:
            str: The local IP address as a string.
            Returns '127.0.0.1' if the local IP cannot be determined.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # The connect call doesn't send data, it just associates the socket
                # with a remote address, which forces the OS to pick a local interface.
                s.connect((remote_server, 80))
                return s.getsockname()[0]
        except socket.error:
            utils_logger.error("Could not determine local IP address. Falling back to localhost '127.0.0.1'.")
            return '127.0.0.1'

    @staticmethod
    def root_page():
        return (
            '/Cast-Center'
            if cfg_mgr.app_config['init_screen'].lower() == 'center'
            else '/'
        )

    @staticmethod
    def select_sc_area(class_obj):
        """ with mouse, draw rectangle to monitor x

        This should run from its own thread to not block main one.
        Area selection (Tkinter) will run on another process and block this thread.
        Update obj.screen_coordinates with coordinates from the selected area.

        Args:
            class_obj: Used to select monitor number
        """

        class_obj.screen_coordinates = []
        monitor = int(class_obj.monitor_number)
        tmp_file = cfg_mgr.app_root_path(f"tmp/sc_{os.getpid()}_file")

        # run in another process and wait for the selection
        area_proc , _ = CASTUtils.mp_setup()
        process = area_proc(target=SCArea.run, args=(monitor, tmp_file))
        process.daemon = True
        utils_logger.debug(f'Process start : {process}')
        process.start()
        process.join()
        utils_logger.debug(f'Resume from Process : {process}')

        # Read saved screen coordinates from shelve file
        try:

            with shelve.open(tmp_file, 'r') as process_file:
                if saved_screen_coordinates := process_file.get("sc_area"):
                    # For Calculate crop parameters
                    class_obj.screen_coordinates = saved_screen_coordinates
                    utils_logger.debug(f"Loaded screen coordinates from shelve: {saved_screen_coordinates}")

        except Exception as er:
            utils_logger.error(f"Error loading screen coordinates from shelve: {er}")


    @staticmethod
    async def api_request(method, endpoint, data=None, params=None):
        """Makes a request to the WLEDVideoSync API using aiohttp.

        Args:
            method (str): The HTTP method (GET, POST, PUT).
            endpoint (str): The API endpoint.
            data (dict, optional): Data to send with the request (for POST/PUT). Defaults to None.
            params (dict, optional): Query parameters for the request. Defaults to None.

        Returns:
            tuple: A tuple containing the status code and the JSON response data (or None if an error occurs).
        """
        server_port = CASTUtils.get_server_port()
        base_url = f"http://127.0.0.1:{server_port}"

        try:
            async with aiohttp.ClientSession() as session:
                url = urllib.parse.urljoin(base_url, endpoint)
                if params:
                    url += f"?{urllib.parse.urlencode(params)}"

                if method == "GET":
                    async with session.get(url, params=params, timeout=5) as response:
                        if response.status == 200:
                            return response.status, await response.json()
                        elif response.status == 400:
                            error_data = await response.text()
                            utils_logger.error(f"GET request error: {error_data}")
                            return response.status, None
                        else:
                            return response.status, None

                elif method == "POST":
                    headers = {'Content-Type': 'application/json'} if data else None
                    json_data = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else None
                    async with session.post(url, params=params, data=json_data, headers=headers, timeout=5) as response:
                        if response.status == 200:
                            return response.status, await response.json()
                        elif response.status == 400:
                            error_data = await response.text()
                            utils_logger.error(f"POST request error: {error_data}")
                            return response.status, None
                        else:
                            return response.status, None

                elif method == "PUT":
                    headers = {'Content-Type': 'application/json'} if data else None
                    json_data = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else None
                    async with session.put(url, params=params, data=json_data, headers=headers, timeout=5) as response:
                        if response.status == 200:
                            return response.status, await response.json()
                        elif response.status == 400:
                            error_data = await response.text()
                            utils_logger.error(f"PUT request error: {error_data}")
                            return response.status, None
                        else:
                            return response.status, None
                else:
                    utils_logger.error(f"Invalid HTTP method: {method}")
                    return None, None # Return (None, None) for invalid method

        except aiohttp.ClientError as er:
            utils_logger.error(f"API request error: {er}")
            return None, None

        except Exception as er:
            utils_logger.error(f"Unexpected exception getting WLEDVideoSync API: {er}")
            return None, None

    @staticmethod
    async def get_wled_info(wled_ip: str) -> dict | None:
        """Fetches general information from WLED, including LED count, using the wled module."""
        try:
            # Instantiate the WLED client
            led = WLED(wled_ip)
            # Update the client state, which fetches /json/info and other data
            await led.update()
            # Return the info dictionary
            return led.info
        except WLEDConnectionError as er:
            utils_logger.error(f"WLED connection error for {wled_ip}: {er}")
            return None
        except WLEDError as er:
            utils_logger.error(f"WLED API error for {wled_ip}: {er}")
            return None
        except Exception as er:
            utils_logger.error(f"Unexpected exception getting WLED info from {wled_ip}: {er}")
            return None

    @staticmethod
    def wled_name_format(wled_name: str) -> str:
        """
        Formats a WLED filename to be at most 32 characters long,
        replacing problematic characters with an underscore and transliterating
        extended characters to their ASCII equivalents.

        Args:
            wled_name (str): The original filename.

        Returns:
            str: The formatted filename, transliterated, cleaned, and truncated.
        """
        # Transliterate extended characters to ASCII (e.g., 'é' -> 'e')
        try:
            wled_name = unidecode(wled_name)
        except Exception as er:
            utils_logger.warning(f"Unidecode failed for '{wled_name}': {er}. Proceeding without transliteration.")

        # Remove the 'yt-tmp-' prefix if it exists
        if wled_name.startswith('yt-tmp-'):
            wled_name = wled_name[7:]

        # Keep only letters, numbers, dot, underscore, and hyphen.
        # Replace all other characters (like #, ?, =, /, space, etc.) with an underscore.
        cleaned_name = re.sub(r'[^\w.-]', '_', wled_name)

        # Replace multiple consecutive underscores with a single one
        cleaned_name = re.sub(r'__+', '_', cleaned_name)

        # Truncate if necessary (WLED filesystem limit is 32 chars total)
        # We aim for a name that, with its extension, fits this limit.
        name_part, ext_part = os.path.splitext(cleaned_name)
        max_base_len = 31 - len(ext_part)

        if max_base_len < 1:  # Handle very long extensions
            max_base_len = 1

        if len(name_part) > max_base_len:
            name_part = name_part[:max_base_len]

        return name_part + ext_part

    @staticmethod
    async def check_wled_file_exists(wled_ip: str, filename: str) -> bool:
        """
        Checks if a specific file exists on the WLED device's filesystem.

        This function performs an HTTP HEAD request to the file's expected URL.
        A 200 OK response indicates the file exists.

        Args:
            wled_ip: The IP address of the WLED device.
            filename: The exact name of the file to check for on the device.
        Returns:
            True if the file exists, False otherwise.
        """

        # WLED serves user-uploaded files from the root of its web server.
        file_url = f"http://{wled_ip}/{filename}"
        utils_logger.debug(f"Checking for file existence with HEAD request at: {file_url}")

        try:
            async with aiohttp.ClientSession() as session:
                # Use a HEAD request for efficiency - we only need the status, not the content.
                async with session.head(file_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        utils_logger.info(f"File '{filename}' found on WLED device {wled_ip}.")
                        return True
                    elif response.status == 404:
                        utils_logger.info(f"File '{filename}' not found on WLED device {wled_ip}.")
                        return False
                    else:
                        utils_logger.warning(f"Unexpected status {response.status} when checking for file on {wled_ip}.")
                        # Assume it doesn't exist to allow upload attempt.
                        return False

        except aiohttp.ClientError as e:
            utils_logger.error(f"Network error checking for file on {wled_ip}: {e}", exc_info=True)
            return False  # Cannot confirm, assume it doesn't exist
        except asyncio.TimeoutError:
            utils_logger.error(f"Timeout checking for file on {wled_ip}.")
            return False  # Cannot confirm, assume it doesn't exist
        except Exception as e:
            utils_logger.error(f"An unexpected error occurred while checking for file on {wled_ip}: {e}", exc_info=True)
            return False  # Cannot confirm, assume it doesn't exist


    @staticmethod
    def wled_upload_file(wled_ip, file_path, content_type: str = 'text/html; charset=UTF-8'):
        """Uploads a GIF file to WLED via the /upload interface.
            there is a limit of 30 chars to wled file name
        Args:
            wled_ip (str): The IP address of the WLED device.
            file_path (str): The path to the file.
            content_type (str): The content type of the file.
        """
        info_url = f"http://{wled_ip}/json/info"
        url = f"http://{wled_ip}/upload"

        try:
            file_path_size_kb = int(os.path.getsize(file_path) / 1024)
            filename = CASTUtils.wled_name_format(os.path.basename(file_path))
            files = {'file': (filename, open(file_path, 'rb'), 'image/gif')}

            # check file space on MCU
            response = requests.get(info_url, timeout=2)  # Add timeout
            response.raise_for_status()
            info_data  = response.json()
            remaining_space_kb = info_data['fs']['t'] - info_data['fs']['u']

            if file_path_size_kb < remaining_space_kb:
                response = requests.post(url, files=files, timeout=10)  # Add timeout
                response.raise_for_status()
                utils_logger.info(f"File uploaded successfully: {response.text} to: {url}")
            else:
                utils_logger.error(f'Not enough space on wled device : {wled_ip}')

        except requests.exceptions.Timeout:
            utils_logger.error(f"Timeout error uploading to: {url}")
        except requests.exceptions.HTTPError as errh:
            utils_logger.error(f"HTTP Error uploading : {errh} to: {url}")
        except requests.exceptions.ConnectionError as errc:
            utils_logger.error(f"Error Connecting to WLED: {errc} at: {url}")
        except requests.exceptions.RequestException as err:
            utils_logger.error(f"Error uploading : {err} to: {url}")

        except Exception as er:
            utils_logger.error(f"An unexpected error occurred: {er}")


    @staticmethod
    async def resize_gif(video_in, video_out, new_w, new_h):
        """Resizes a  GIF file using PyAV.

        Args:
            video_in (str): Path to the input video/GIF file.
            video_out (str): Path to the output resized video/GIF file.
            new_w (int): New width.
            new_h (int): New height.
        """
        try:
            container_in = av.open(video_in)
            if container_in.format.name == 'gif':
                # For GIFs, resize frames individually and create a new GIF
                frames = []
                stream = container_in.streams.video[0]
                for frame in container_in.decode(stream):
                    img = frame.to_image()
                    img = np.array(img)
                    resized_frame = cv2.resize(img, (new_w, new_h))
                    frames.append(Image.fromarray(resized_frame))

                frames[0].save(video_out,
                               save_all=True,
                               append_images=frames[1:],
                               loop=0,
                               duration=stream.average_rate.denominator)

            else:
                utils_logger.error(f'Not a GIF file : {video_in}')

            container_in.close()

        except Exception as er:
            utils_logger.error(f"Error resizing GIF: {er}")


    @staticmethod
    async def resize_video(video_in, video_out, new_w, new_h):
        """Resizes a video  file using PyAV.

        Args:
            video_in (str): Path to the input video file.
            video_out (str): Path to the output resized video file.
            new_w (int): New width.
            new_h (int): New height.
        """
        try:
            container_in = av.open(video_in)
            container_out = av.open(video_out, mode='w')

            in_stream = container_in.streams.video[0]
            # For other video formats, use reformat and libx264
            out_stream = container_out.add_stream(codec_name='libx264', rate=in_stream.average_rate)
            out_stream.width = new_w
            out_stream.height = new_h
            out_stream.pix_fmt = 'yuv420p'

            for frame in container_in.decode(video=0):
                frame = frame.reformat(width=new_w, height=new_h)
                for packet in out_stream.encode(frame):
                    container_out.mux(packet)

            # Flush stream
            for packet in out_stream.encode():
                container_out.mux(packet)

            container_out.close()
            container_in.close()

        except Exception as er:
            utils_logger.error(f"Error resizing video: {er}")


    @staticmethod
    async def video_to_gif(video_file, gif_file, width = None, height = None, loop: int = 0, duration: int = 100):
        """Convert an MP4 file to a GIF.

        Reads frames from an MP4 file using pyav, resize & converts them to RGB numpy arrays,
        and then saves them as a GIF using Pillow.
        duration : time frame display,default to 100ms. e.g: 10 images * 100 duration = 1 second = 10fps
        """

        # Open the video file using pyav
        container = av.open(video_file)

        # Read the frames from the first video stream
        frames = []
        for frame in container.decode(video=0):
            # resize
            if width is not None and height is not None:
                frame = frame.reformat(width=width, height=height)
            # Convert the frame to numpy array (RGB format)
            img = frame.to_image()
            img = np.array(img)

            # Append the frame to the list
            frames.append(img)

        # Create a GIF from the frames
        frames_pil = [Image.fromarray(frame) for frame in frames]
        frames_pil[0].save(gif_file, save_all=True, append_images=frames_pil[1:], loop=loop, duration=duration, disposal=2)
        #
        container.close()

    @staticmethod
    def get_video_dimensions(video_path):
        """Retrieves the width and height of a video file.

        Args:
            video_path (str): Path to the video file.

        Returns:
            tuple: A tuple containing the width and height of the video, or (None, None) if an error occurs.
        """
        try:
            container = av.open(video_path)
            video_stream = container.streams.video[0]
            width = video_stream.width
            height = video_stream.height
            container.close()
            return width, height
        except Exception as er:
            utils_logger.error(f"Error getting video dimensions: {er}")
            return None, None

    @staticmethod
    def extract_filename(path_or_url):
        """Extracts the filename from a local path or URL.

        Args:
            path_or_url (str): The local path or URL.

        Returns:
            str: The extracted filename, or None if extraction fails.
        """
        try:
            parsed_url = urllib.parse.urlparse(path_or_url)
            if parsed_url.scheme and not re.match(r'^[a-zA-Z]$', parsed_url.scheme):  # Check for valid URL scheme (not drive letter)
                return os.path.basename(parsed_url.path)
            else:  # It's a local path
                return os.path.basename(path_or_url)
        except Exception as er:
            utils_logger.error(f"Error extracting filename: {er}")
            return None

    @staticmethod
    def is_compiled():
        """Determine if the application is running as a compiled executable.

        Returns True if the application is running in a frozen or compiled state, otherwise False.

        Returns:
            bool: True if running as a compiled executable, False otherwise.
        """
        return bool(getattr(sys, 'frozen',False) or '__compiled__' in globals())

    @staticmethod
    def clean_tmp():
        """Remove temporary, YouTube, and image files based on configuration.

        Cleans up temporary files, YouTube downloads, and image files from their respective directories
        according to the application's configuration settings.
        """
        try:

            # some cleaning
            utils_logger.info('Cleaning ...')
            utils_logger.debug('Remove tmp files')
            for tmp_filename in PathLib("tmp/").glob("*_file*"):
                tmp_filename.unlink()

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
            utils_logger.error(f'Error to remove tmp files : {error}')


    @staticmethod
    def get_queue_manager_settings():
        """Retrieve the IP address and port for the queue manager.

        Returns the IP address and port from the configuration, or defaults if not set.

        Returns:
            tuple: A tuple containing the IP address (str) and port (int) for the queue manager.
        """
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
    def attach_to_sl_manager(sl_ip=None, sl_port=None):
        """Create and return a SharedListClient connected to the SL manager.

        Retrieves the SL manager's IP and port from configuration and returns a SharedListClient instance.

        Returns:
            SharedListClient: An instance connected to the configured SL manager.
        """
        from src.utl.sharedlistclient import SharedListClient

        #
        if sl_ip is None or sl_port is None:
            ip, port = CASTUtils.get_queue_manager_settings()

        else:
            ip = sl_ip
            port = sl_port

        return SharedListClient(sl_ip_address=ip, sl_port=port)

    @staticmethod
    def attach_to_manager_list(list_name, manager_ip=None, manager_port=None):
        """Attach to a shared manager list and retrieve its dimensions.

        Connects to the shared list manager and attaches to the specified queue,
        returning the shared list object and its width and height.

        Args:
            list_name (str): The name of the shared queue to attach to.
            manager_ip (str): The IP address of the SL manager.
            manager_port (int): The port of the SL manager.

        Returns:
            tuple: A tuple containing the shared list object, its width, and its height.
            Returns (None, None, None) if connection fails.
        """
        sl = None
        width = None
        height = None

        try:
            client =  CASTUtils.attach_to_sl_manager(manager_ip, manager_port)
            if client.connect():
                sl = client.attach_to_shared_list(list_name)
                sl_info = client.get_shared_list_info(list_name)
                width = sl_info['w']
                height = sl_info['h']
        except Exception as er:
            utils_logger.error(f'Error  {er}  to attach to : {list_name} ')

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

        with open(cfg_mgr.app_root_path(f'assets/version-{PLATFORM}.json'), 'r') as file:
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
            utils_logger.info(f'In update_ini_key , ini file : {file_path}')
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
            utils_logger.info(f"INI Updated '{key}' to '{new_value}' in section '{section}'.")
        except (NameError, AttributeError):
            # this will be print only during init app as logger is not yet defined (NameError)
            print(f"INI Updated '{key}' to '{new_value}' in section '{section}'.")


    @staticmethod
    def mp_setup():
        """
        Set multiprocess context: fork, spawn, etc.

        Notes:
        - On Linux/macOS, default is 'fork', but 'spawn' can be forced.
        - spawn/forkserver may behave unpredictably in frozen binaries.
        - fork is faster but unsafe with threads in some cases.
        """
        import multiprocessing
        if PLATFORM in ['darwin', 'linux']:
            try:
                # Use explicit context to avoid conflicts
                ctx = multiprocessing.get_context('spawn')
                utils_logger.debug("Multiprocessing context set to 'spawn'.")
                return ctx.Process, ctx.Queue
            except RuntimeError:
                utils_logger.debug("Multiprocessing start method already set.")
                ctx = multiprocessing.get_context()
                return ctx.Process, ctx.Queue
        else:
            ctx = multiprocessing.get_context()
            return ctx.Process, ctx.Queue

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
                utils_logger.debug(f'Stopping Child Process for Preview if any : {t_name}')
                sl_process.kill()
        except Exception as err:
            utils_logger.error(f'Error on SL clean : {err}')

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
    async def get_yt_video_url(video_url, iformat="best"):
        """Retrieve the direct video URL from a YouTube link.

        Extracts and returns the direct video URL for the specified YouTube link and format.
        Returns None if no URL is found.

        Args:
            video_url (str): The YouTube video URL.
            iformat (str, optional): The desired video format. Defaults to "best".

        Returns:
            str or None: The direct video URL if found, otherwise None.
        """
        ydl_opts = {
            'format': iformat,
            'noplaylist': True,  # Prevents playlist processing
            'quiet': True,
            'extract_flat': False,  # Ensure we get detailed info
        }

        with YTdl(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        # Ensure we return only one URL
        if 'url' in info:
            return info['url']
        elif 'entries' in info and isinstance(info['entries'], list) and len(info['entries']) > 0:
            return info['entries'][0].get('url', None)

        return None  # If no URL found

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

        with YTdl(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return info

    @staticmethod
    async def youtube_download(yt_url: str = None, interactive: bool = True):
        """download video from YouTube"""

        # select from ini file
        download_format = cfg_mgr.custom_config['yt_format']

        def post_hook(d):
            if d['status'] == 'finished':
                final_filename = d.get('info_dict').get('_filename')
                CASTUtils.yt_file_name = final_filename
                CASTUtils.yt_file_size_remain_bytes = 0
                utils_logger.debug(f"Finished Post Process {final_filename}")

        if interactive:
            """
            if log_ui is not None:
                handler = LogElementHandler(log_ui)
                utils_logger.addHandler(handler)
                ui.context.client.on_disconnect(lambda: utils_logger.removeHandler(handler))
            """
            def progress_hook(d):
                if d['status'] == 'downloading':
                    if 'total_bytes_estimate' in d:
                        CASTUtils.yt_file_size_bytes = d['total_bytes_estimate']
                        CASTUtils.yt_file_size_remain_bytes = d['total_bytes_estimate'] - d['downloaded_bytes']
                    if 'total_bytes' in d:
                        CASTUtils.yt_file_size_bytes = d['total_bytes']
                        CASTUtils.yt_file_size_remain_bytes = d['total_bytes'] - d['downloaded_bytes']

                    utils_logger.debug(f"Downloading: {d['_percent_str']} of "
                                f"{d['_total_bytes_str']} at {d['_speed_str']} ETA {d['_eta_str']}")

                elif d['status'] == 'finished':
                    utils_logger.debug(f"Finished downloading {d['filename']}")

            ydl_opts = {
                'format': f'{download_format}',
                'paths': {'temp': cfg_mgr.app_root_path('tmp')},
                'outtmpl': cfg_mgr.app_root_path('media/yt-tmp-%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'postprocessor_hooks': [post_hook],
                'noplaylist': True,
                'ignoreerrors': True,
                'quiet': True,
            }

        else:

            ydl_opts = {
                'format': f'{download_format}',
                'paths': {'temp': cfg_mgr.app_root_path('tmp')},
                'outtmpl': cfg_mgr.app_root_path('media/yt-tmp-%(title)s.%(ext)s'),
                'postprocessor_hooks': [post_hook],
                'noplaylist': True,
                'ignoreerrors': True,
                'quiet': True,
            }

        try:

            CASTUtils.yt_file_size_remain_bytes = 1024
            CASTUtils.yt_file_size_bytes = 1024

            ydl = YTdl(ydl_opts)
            await run.io_bound(ydl.download, url_list=yt_url)

        except Exception as err:
            CASTUtils.yt_file_name = ''
            utils_logger.error(f'Youtube download error : {err}')

        return CASTUtils.yt_file_name

    @staticmethod
    def get_server_port():
        """ Retrieve server port number """

        server_port = 0

        try:
            # read file
            with shelve.open(WLED_PID_TMP_FILE, 'r') as db:
                server_port = db['server_port']
        except Exception as er:
            utils_logger.warning(f'Using 8080 as Not able to retrieve Server Port  from {WLED_PID_TMP_FILE}: {er}')
            server_port = 8080
        finally:
            if server_port == 0:
                utils_logger.error(f'Server Port should not be 0 from {WLED_PID_TMP_FILE}')


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
                utils_logger.debug(f'WLED matrix : {str(matrix["w"])} x {str(matrix["h"])}')
            await wled.close()
        except Exception as error:
            utils_logger.error(traceback.format_exc())
            utils_logger.error(f'An exception occurred: {error}')
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
            utils_logger.error(f'Not able to get WLED info : {error}')
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
                if not await wled.request(
                    uri='/json', method='POST', data={'on': on, 'live': live}
                ):
                    return False
                await wled.close()
                return True
            else:
                utils_logger.warning(f"Not able to connect to WLED device: {host}")
                return False
        except Exception as error:
            utils_logger.error(traceback.format_exc())
            utils_logger.error(f"Not able to set WLED device {host} in 'live' mode. Got this error : {error}")
            await wled.close()
            return False
        
    @staticmethod
    async def dev_list_update():
        """
        Update Media device list depend on OS
        """

        CASTUtils.dev_list = await CASTUtils.video_device_list()


    @staticmethod
    async def video_device_list():

        devices_list = []
        backend = None

        if PLATFORM == 'darwin':
            backend = cv2.CAP_AVFOUNDATION
        elif PLATFORM == 'linux':
            backend = cv2.CAP_V4L2
        elif PLATFORM == 'win32':
            backend = cv2.CAP_DSHOW

        devices_list.extend(
            f'{camera_info.index},{camera_info.name}'
            for camera_info in enumerate_cameras(backend)
        )
        return devices_list


    # validate json received by ws
    @staticmethod
    def validate_ws_json_input(input_data):
        """
        Validate data received via WS comply to action/type/param/
            Some params are mandatory
        """

        if not isinstance(input_data, dict):
            utils_logger.error('WEBSOCKET: input not valid format--> need dict')
            return False

        if "action" not in input_data:
            utils_logger.error('WEBSOCKET: action key is missing')
            return False

        action = input_data["action"]
        if not isinstance(action, dict):
            utils_logger.error('WEBSOCKET: input not valid format--> need dict')
            return False

        if "type" not in action or not isinstance(action["type"], str):
            utils_logger.error('WEBSOCKET: need type str')
            return False

        if "param" not in action or not isinstance(action["param"], dict):
            utils_logger.error('WEBSOCKET: missing "param" or wrong type')
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
        prefix = {s: 1 << (i + 1) * 10 for i, s in enumerate(symbols)}
        for s in reversed(symbols):
            if abs(n) >= prefix[s]:
                value = float(n) / prefix[s]
                return '%.1f%s' % (value, s)

        return f"{n}B"

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
        with contextlib.suppress(ValueError):
            ipaddress.ip_address(ip_string)
            return True
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

            result = wled_ping(ip_address, timeout=timeout)
            return result is not None

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
                return result == 0
            except Exception as error:
                utils_logger.error(traceback.format_exc())
                utils_logger.error(f'Error on check IP : {error}')
                return False
            finally:
                # Close the socket
                sock.close()

    @staticmethod
    def check_and_clean_todo_list(class_name):
        """
        clean the to do list for a Class
        """
        utils_logger.warning(f'Something wrong happened. To Do list has been cleared for {class_name}')
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
                utils_logger.error(f'Image already exist : {file_path}')
            else:
                with open(file_path, "wb") as f:
                    image.save(f, "JPEG")

                utils_logger.debug(f'Image saved to : {file_path}')

            return True

        except Exception as err:
            utils_logger.error(f'Error to save image from {url} :  {err}')

            return False

    @staticmethod
    async def is_image_url(url, timeout: int = 2):
        """ detect if url contains an image """

        try:
            response = requests.get(url, stream=True, timeout=timeout)
            content_type = response.headers.get('Content-Type')
            return bool(content_type and content_type.startswith('image/'))
        except requests.RequestException as err:
            utils_logger.error(f"Error checking URL: {err}")
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

    @staticmethod
    async def get_all_running_hosts(inter_proc_file=None):
        """
        Retrieves a unique list of all IP hosts from all currently running casts.

        This function queries all active Desktop and Media casts for their
        device information and compiles a single, deduplicated list of all
        IP addresses they are streaming to.

        Data are saved into inter-process file for other components to use.

        Returns:
            list: A sorted list of unique IP addresses.
        """
        from mainapp import util_casts_info

        if inter_proc_file is None:
            inter_proc_file = WLED_PID_TMP_FILE

        all_hosts = set()
        info_data = await util_casts_info()

        if info_data and 't_info' in info_data:
            for thread_info in info_data['t_info'].values():
                devices = thread_info.get('data', {}).get('devices', [])
                for device_ip in devices:
                    all_hosts.add(device_ip)

        # if no casts running we set 127.0.0.1 as default
        if not all_hosts:
            all_hosts.add('127.0.0.1')

        dev_list = sorted(all_hosts)

        # Shelve file extension handling can differ between Python versions.
        # Conditionally check for the .dat file for better compatibility.
        file_to_check = CASTUtils.get_shelve_file_path(inter_proc_file)
        if os.path.exists(file_to_check):
            # Store all running hosts in the inter-process file for other components to use
            with shelve.open(inter_proc_file, writeback=True) as proc_file:
                proc_file["all_hosts"] = dev_list
        else:
            utils_logger.warning(f"Inter-process file '{file_to_check}' not found. Devices list will not be stored.")

        return dev_list

    @staticmethod
    def enable_win_console():
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 4)


    @staticmethod
    def handle_command_line_args(argv, obj_name=None):
        """
        Parses command-line arguments using argparse to configure the application state.

        This function handles flags like --wled, --ip, --width, --height, etc.,
        and updates the Desktop object accordingly. It's designed to be called
        when the application is launched with specific child-process flags like
        `--run-mobile-server`.

        Args:
            argv (list): The list of command-line arguments (e.g., sys.argv).
            obj_name : Cast object e.g. Desktop

        Returns:
            bool: True if parsing is successful, False otherwise.
            args: Parsed command-line arguments.
        """
        import argparse
        # We only parse arguments after the script name
        parser = argparse.ArgumentParser(description="WLEDVideoSync Child Process Runner")

        #
        parser.add_argument('--run-sys-charts', action='store_true',
                            help='Run Charts server application. (add --more to see more options)')

        # Group for mobile server arguments
        parser.add_argument('--run-mobile-server', action='store_true', help='Run Mobile server application.')
        #
        mobile_group = parser.add_argument_group('Mobile Server Options', 'These arguments are only used with --run-mobile-server')
        mobile_group.add_argument('--preview', action='store_true', help='Enable Preview Window for the Desktop cast.')
        mobile_group.add_argument('--no-text', action='store_true', help='Disable text overlay for the Desktop cast.')
        mobile_group.add_argument('--wled', action='store_true', help='Set Desktop cast to WLED mode to auto-detect matrix size.')
        mobile_group.add_argument('--ip', type=str, help='Set the target IP address for the Desktop cast.')
        mobile_group.add_argument('--width', type=int, help='Set the width for the Desktop cast matrix.')
        mobile_group.add_argument('--height', type=int, help='Set the height for the Desktop cast matrix.')


        # Common arguments used by multiple modes
        parser.add_argument('--file', type=str, default = '', help='Absolute path of the inter-process file (shelve).')
        parser.add_argument('--dark', action='store_true', help='If present set dark mode On')

        # Parse known arguments, ignoring others that might be for the parent process
        args, _ = parser.parse_known_args(argv[1:])

        if obj_name is not None:
            if args.wled:
                obj_name.wled = True
                utils_logger.debug("Command-line override: WLED mode enabled.")

            if args.no_text:
                obj_name.allow_text_animator = False
                utils_logger.debug("Command-line override: Text overlay mode disabled.")

            if args.width is not None:
                obj_name.scale_width = args.width
                utils_logger.debug(f"Command-line override: scale_width set to {obj_name.scale_width}")

            if args.height is not None:
                obj_name.scale_height = args.height
                utils_logger.debug(f"Command-line override: scale_height set to {obj_name.scale_height}")

            if args.ip is not None:
                obj_name.host = args.ip
                utils_logger.debug(f"Command-line override: host set to {obj_name.host}")

            if args.preview:
                obj_name.preview = True
                utils_logger.debug(f"Command-line override: preview set to {obj_name.preview}")

        return True, args

    @staticmethod
    def show_splash_screen():
        """
        Displays a splash screen using tkinter.
        Should run in a separate process for macOS compatibility.
        macOS fix included so the splash window actually closes.
        """
        import tkinter as tk
        from PIL import Image, ImageTk

        def force_close():
            """macOS-safe forced window close."""
            try:
                root.update_idletasks()
                root.update()
            except:
                pass

            try:
                root.quit()
            except:
                pass

            try:
                root.destroy()
            except:
                pass

        try:
            root = tk.Tk()
            transparent_color = '#abcdef'

            root.config(bg=transparent_color)
            root.overrideredirect(True)

            # Bring the window to the front (may not be honored on all window managers)
            try:
                root.attributes('-topmost', True)
            except Exception:
                # attributes may not be available on some platforms
                pass

            # Load splash image
            image_path = cfg_mgr.app_root_path("splash-screen.png")
            pil_image = Image.open(image_path)
            splash_image = ImageTk.PhotoImage(pil_image)

            img_width = splash_image.width()
            img_height = splash_image.height()

            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x = (screen_width // 2) - (img_width // 2)
            y = (screen_height // 2) - (img_height // 2)
            root.geometry(f"{img_width}x{img_height}+{x}+{y}")

            tk.Label(root, image=splash_image, bg=transparent_color, borderwidth=0).pack()

            # Bring the window to transparent background (may not be honored on all window managers)
            try:
                root.wm_attributes('-transparentcolor', transparent_color)
            except Exception:
                pass

            # Close splash after 3 seconds (calls forced macOS-safe close)
            root.after(3000, force_close)

            root.protocol("WM_DELETE_WINDOW", force_close)

            root.mainloop()
            force_close()

        except Exception as er:
            utils_logger.error(f"Failed to show splash screen: {er}")

    @staticmethod
    def get_shelve_file_path(base_path: str) -> str:
        """
        Returns the appropriate shelve file path to check for existence,
        accounting for Python version differences.

        On Python < 3.13, shelve often creates a `.dat` file, so we check for that.
        On Python >= 3.13, it uses a single file with no extension.

        Args:
            base_path: The base path of the shelve file.

        Returns:
            The path that should be checked with os.path.exists().
        """
        if PLATFORM == "darwin":
            return f'{base_path}.db' if sys.version_info < (3, 13) else base_path
        elif PLATFORM == "linux":
            return f'{base_path}.pag' if sys.version_info < (3, 13) else base_path
        else:
            return f'{base_path}.dat' if sys.version_info < (3, 13) else base_path
