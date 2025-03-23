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
import traceback
import json
import re
import platform
import subprocess
import configparser
import io
import pywinctl as pwc
import socket
import ipaddress
import requests
import multiprocessing

import av
import cv2
import numpy as np

from wled import WLED
from zeroconf import ServiceBrowser, Zeroconf
from nicegui import run
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
    def wled_name_format(wled_name):
        """Formats a WLED filename to be at most 32 characters long.

         Args:
             wled_name (str): The original filename.

         Returns:
             str: The formatted filename, truncated to 32 characters if necessary.
         """
        # remove unicode control char
        # wled_name = wled_name.encode('UTF-8', 'ignore').decode('UTF-8')
        # remove YT prefix
        wled_name = wled_name.replace('yt-tmp-','')
        #
        wled_name = wled_name.replace('/', '-')
        wled_name = wled_name.replace(' ', '')
        #
        if len(wled_name) > 28:
            name, ext = os.path.splitext(wled_name)
            return wled_name[:28] + ext  # Truncate to 32 characters
        return wled_name

    @staticmethod
    def wled_upload_gif_file(wled_ip, gif_path):
        """Uploads a GIF file to WLED via the /upload interface.
            there is a limit of 32 chars to wled file name
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
            response = requests.get(info_url, timeout=2)  # Add timeout
            response.raise_for_status()
            info_data  = response.json()
            remaining_space_kb = info_data['fs']['t'] - info_data['fs']['u']

            if gif_path_size_kb < remaining_space_kb:
                response = requests.post(url, files=files, timeout=10)  # Add timeout
                response.raise_for_status()
                cfg_mgr.logger.info(f"GIF uploaded successfully: {response.text} to: {url}")
            else:
                cfg_mgr.logger.error(f'Not enough space on wled device : {wled_ip}')

        except requests.exceptions.Timeout:
            cfg_mgr.logger.error(f"Timeout error uploading GIF to: {url}")
        except requests.exceptions.HTTPError as errh:
            cfg_mgr.logger.error(f"HTTP Error uploading GIF: {errh} to: {url}")
        except requests.exceptions.ConnectionError as errc:
            cfg_mgr.logger.error(f"Error Connecting to WLED: {errc} at: {url}")
        except requests.exceptions.RequestException as err:
            cfg_mgr.logger.error(f"Error uploading GIF: {err} to: {url}")


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
                cfg_mgr.logger.error(f'Not a GIF file : {video_in}')

            container_in.close()

        except Exception as er:
            print(f"Error resizing GIF: {er}")


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
            print(f"Error resizing video: {er}")


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
            print(f"Error getting video dimensions: {er}")
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
            print(f"Error extracting filename: {er}")
            return None

    @staticmethod
    def test_compiled():
        return bool(getattr(sys, 'frozen',False) or '__compiled__' in globals())

    @staticmethod
    def clean_tmp():
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
        except Exception as err:
            cfg_mgr.logger.error(f'Error on SL clean : {err}')

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
    async def youtube_download(yt_url: str = None, interactive: bool = True):
        """download video from YouTube"""

        # select from ini file
        download_format = cfg_mgr.custom_config['yt_format']

        def post_hook(d):
            if d['status'] == 'finished':
                final_filename = d.get('info_dict').get('_filename')
                CASTUtils.yt_file_name = final_filename
                CASTUtils.yt_file_size_remain_bytes = 0
                cfg_mgr.logger.debug(f"Finished Post Process {final_filename}")

        if interactive:
            """
            if log_ui is not None:
                handler = LogElementHandler(log_ui)
                cfg_mgr.logger.addHandler(handler)
                ui.context.client.on_disconnect(lambda: cfg_mgr.logger.removeHandler(handler))
            """
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

            ydl = YoutubeDL(ydl_opts)
            await run.io_bound(ydl.download, url_list=yt_url)

        except Exception as err:
            CASTUtils.yt_file_name = ''
            cfg_mgr.logger.error(f'Youtube download error : {err}')

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
            cfg_mgr.logger.warning(f'Error to retrieve Server Port  from {tmp_file}: {er}')
            server_port = 99
        finally:
            if server_port == 0:
                cfg_mgr.logger.error(f'Server Port should not be 0 from {tmp_file}')

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
                if not await wled.request(
                    uri='/json', method='POST', data={'on': on, 'live': live}
                ):
                    return False
                await wled.close()
                return True
            else:
                cfg_mgr.logger.warning(f"Not able to connect to WLED device: {host}")
                return False
        except Exception as error:
            cfg_mgr.logger.error(traceback.format_exc())
            cfg_mgr.logger.error(f"Not able to set WLED device {host} in 'live' mode. Got this error : {error}")
            await wled.close()
            return False
        
    @staticmethod
    def get_window_rect(title):
        """Find window position and size using pywinctl (cross-platform)."""
        
        try:
            if win := pwc.getWindowsWithTitle(title):
                win = win[0]  # Get the first matching window
                if win.isMinimized:
                    win.restore()  # Restore if minimized

                win.activate()  # Bring window to front
                time.sleep(0.1)  # Wait for the window to be active

                return win.left, win.top, win.width, win.height
            
        except Exception as er:
            cfg_mgr.logger.error(f"Not able to retrieve info for window name {title}. Error: {er}")
            
        return None

    @staticmethod
    def active_window():
        """ Provide active window title """

        return pwc.getActiveWindow().title

    @staticmethod
    async def windows_titles():
        """ Provide a list of all window titles / hWnd by applications """

        try:
            
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
            data = await run.cpu_bound(pwc.getAllWindowsDict)
            # Convert dictionary to JSON
            all_windows = json.dumps(data, default=custom_serializer, ensure_ascii=False, indent=4)
            windows_by_app = json.loads(all_windows)

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
                        if numbers_in_brackets := re.findall(r'\[(\d+)\]', name):
                            devicenumber = int(numbers_in_brackets[0])

                        devname = (
                            match[1]
                            if (match := re.search(r"\[\d+\] (.*)", name))
                            else "unknown"
                        )
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
            return bool(content_type and content_type.startswith('image/'))
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
