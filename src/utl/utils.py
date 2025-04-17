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
import urllib.parse
import time
import shelve
import os
import sys
import inspect
import traceback
import json
import re
import platform
import subprocess
import configparser
import io
import socket
import ipaddress
import requests
import aiohttp
import multiprocessing
import av
import cv2
import numpy as np

try:
    from yt_dlp import YoutubeDL as YTdl
except Exception as e:
    print(f'INFO : this is Not a YT version: {e}')

from str2bool import str2bool
from pathlib import Path as PathLib
from wled import WLED
from zeroconf import ServiceBrowser, Zeroconf
from nicegui import run
from PIL import Image
from unidecode import unidecode
from coldtype.text.reader import Font

from src.gui.tkarea import ScreenAreaSelection as SCArea

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.utils')
utils_logger = logger_manager.logger

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
    def root_page():
        return (
            '/Cast-Center'
            if cfg_mgr.app_config['init_screen'].lower() == 'center'
            else '/'
        )

    @staticmethod
    async def select_sc_area(class_obj):
        """ with mouse, draw rectangle to monitor x """

        monitor = int(class_obj.monitor_number)
        tmp_file = cfg_mgr.app_root_path(f"tmp/{os.getpid()}_file")

        # run in no blocking mode, another process for macOS else thread
        if sys.platform.lower() == 'darwin':

            await run.cpu_bound(SCArea.run, monitor, tmp_file)

            # Read saved screen coordinates from shelve file
            try:

                with shelve.open(tmp_file, 'r') as process_file:
                    if saved_screen_coordinates := process_file.get("sc_area"):
                        SCArea.screen_coordinates = saved_screen_coordinates
                        utils_logger.debug(f"Loaded screen coordinates from shelve: {saved_screen_coordinates}")

            except Exception as er:
                utils_logger.error(f"Error loading screen coordinates from shelve: {er}")
        else:

            await run.io_bound(SCArea.run, monitor, tmp_file)

        # For Calculate crop parameters
        class_obj.screen_coordinates = SCArea.screen_coordinates
        #
        utils_logger.debug(f'Monitor infos: {SCArea.monitors}')
        utils_logger.debug(f'Area Coordinates: {SCArea.coordinates} from monitor {monitor}')
        utils_logger.debug(f'Area screen Coordinates: {SCArea.screen_coordinates} from monitor {monitor}')


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

    @staticmethod
    def wled_name_format(wled_name):
        """Formats a WLED filename to be at most 32 characters long,
           replacing extended characters with ASCII equivalents.

         Args:
             wled_name (str): The original filename.

         Returns:
             str: The formatted filename, transliterated, cleaned, and truncated if necessary.
         """
        # Transliterate extended characters to ASCII
        try:
            wled_name = unidecode(wled_name)  # <-- Apply unidecode here
        except Exception as er:
            utils_logger.warning(f"Unidecode failed for '{wled_name}': {er}. Proceeding without transliteration.")
            # Fallback or re-raise depending on desired behavior

        # remove YT prefix
        wled_name = wled_name.replace('yt-tmp-', '')
        #
        wled_name = wled_name.replace('/', '-')
        wled_name = wled_name.replace(' ', '')  # Remove spaces after transliteration

        # Truncate if necessary (adjust length if needed, WLED limit is 32)
        # Let's keep it slightly shorter to be safe, e.g., 30 + extension
        max_base_len = 30
        if len(wled_name) > max_base_len:
            name, ext = os.path.splitext(wled_name)
            # Ensure the base name doesn't exceed the limit after adding extension
            allowed_name_len = max_base_len - len(ext)
            if allowed_name_len < 1:  # Handle cases with very long extensions
                allowed_name_len = 1
            return name[:allowed_name_len] + ext
        return wled_name


    @staticmethod
    def wled_upload_gif_file(wled_ip, gif_path):
        """Uploads a GIF file to WLED via the /upload interface.
            there is a limit of 30 chars to wled file name
        Args:
            wled_ip (str): The IP address of the WLED device.
            gif_path (str): The path to the GIF file.
        """

        gif_path_size_kb = int(os.path.getsize(gif_path) / 1024)
        info_url = f"http://{wled_ip}/json/info"
        url = f"http://{wled_ip}/upload"
        filename = CASTUtils.wled_name_format(os.path.basename(gif_path))
        files = {'file': (filename, open(gif_path, 'rb'), 'image/gif')}

        try:
            # check file space on MCU
            response = requests.get(info_url, timeout=2)  # Add timeout
            response.raise_for_status()
            info_data  = response.json()
            remaining_space_kb = info_data['fs']['t'] - info_data['fs']['u']

            if gif_path_size_kb < remaining_space_kb:
                response = requests.post(url, files=files, timeout=10)  # Add timeout
                response.raise_for_status()
                utils_logger.info(f"GIF uploaded successfully: {response.text} to: {url}")
            else:
                utils_logger.error(f'Not enough space on wled device : {wled_ip}')

        except requests.exceptions.Timeout:
            utils_logger.error(f"Timeout error uploading GIF to: {url}")
        except requests.exceptions.HTTPError as errh:
            utils_logger.error(f"HTTP Error uploading GIF: {errh} to: {url}")
        except requests.exceptions.ConnectionError as errc:
            utils_logger.error(f"Error Connecting to WLED: {errc} at: {url}")
        except requests.exceptions.RequestException as err:
            utils_logger.error(f"Error uploading GIF: {err} to: {url}")


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
    def test_compiled():
        return bool(getattr(sys, 'frozen',False) or '__compiled__' in globals())

    @staticmethod
    def clean_tmp():
        try:

            # some cleaning
            utils_logger.info('Cleaning ...')
            utils_logger.debug('Remove tmp files')
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
            if client.connect():
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
        tmp_file = 'unknown'

        try:
            # get pid
            p_pid = os.getpid()
            tmp_file = cfg_mgr.app_root_path(f"tmp/{p_pid}_file")
            # read file
            with shelve.open(tmp_file) as db:
                server_port = db['server_port']
        except Exception as er:
            utils_logger.debug(f'Error to retrieve Server Port  from {tmp_file}: {er}')
            server_port = 8080
        finally:
            if server_port == 0:
                utils_logger.error(f'Server Port should not be 0 from {tmp_file}')

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

        devicenumber = 0
        devices_list = []

        if platform.system().lower() == 'darwin':
            try:
                import av

                with av.logging.Capture(True):  # this will capture av output
                    av.open('', 'r', format='avfoundation', options={'list_devices': 'True'})

            except Exception as error:
                utils_logger.error(traceback.format_exc())
                utils_logger.error(f'An exception occurred: {error}')

        # linux
        if platform.system().lower() == 'linux':
            from linuxpy.video import device as linux_dev

            dev = linux_dev.iter_devices()
            typedev = 'VIDEO'
            devices_list.extend(
                (str(item), typedev, i) for i, item in enumerate(dev, start=1)
            )

        elif platform.system().lower() == 'windows':
            from pygrabber.dshow_graph import FilterGraph

            graph = FilterGraph()
            devices = graph.get_input_devices()
            typedev = 'video'
            for item in devices:
                devname = item
                devices_list.append((devname, typedev, devicenumber))
                devicenumber += 1

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
        utils_logger.debug('Scanning network devices ...')
        time.sleep(self.duration)
        zeroconf.close()
        utils_logger.debug('Scanning network devices ... Done')
