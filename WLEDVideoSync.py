# Compilation mode, standalone everywhere
# nuitka-project: --nofollow-import-to=doctest
# nuitka-project: --noinclude-default-mode=error
# nuitka-project: --include-raw-dir=xtra=xtra
# nuitka-project-if: {OS} == "Windows":
#   nuitka-project: --onefile-windows-splash-screen-image={MAIN_DIRECTORY}/splash-screen.png
# nuitka-project-if: os.getenv("DEBUG_COMPILATION", "no") == "yes":
#   nuitka-project: --force-stdout-spec=WLEDVideoSync.out.txt
#   nuitka-project: --force-stderr-spec=WLEDVideoSync.err.txt
# nuitka-project-if: {OS} == "Linux":
#   nuitka-project: --include-module=gi
#   nuitka-project: --include-module=qtpy
"""
a : zak-45
d : 07/04/2024
v : 1.0.0

Main WLEDVideoSync.

"""
import sys
import shelve
from subprocess import Popen

from nicegui import ui, app , native

import os

import tkinter as tk
import CastAPI

from tkinter import PhotoImage
from src.utl.utils import CASTUtils as Utils
from str2bool import str2bool
from configmanager import ConfigManager


cfg_mgr = ConfigManager(logger_name='WLEDLogger')

Process, Queue = Utils.mp_setup()


def run_gui():

    server_port = None
    server_ip = None

    print('start NiceGui')

    if "NUITKA_ONEFILE_PARENT" not in os.environ and cfg_mgr.server_config is not None:
        server_ip = cfg_mgr.server_config['server_ip']
        if not Utils.validate_ip_address(server_ip):
            cfg_mgr.logger.error(f'Bad server IP: {server_ip}')
            sys.exit(1)

        server_port = cfg_mgr.server_config['server_port']

        if server_port == 'auto':
            server_port = native.find_open_port()
        else:
            server_port = int(cfg_mgr.server_config['server_port'])

        if server_port not in range(1, 65536):
            cfg_mgr.logger.error(f'Bad server Port: {server_port}')
            sys.exit(2)

    # store server port info for others processes
    pid = os.getpid()

    pid_tmp_file = cfg_mgr.app_root_path(f"tmp/{pid}_file")
    proc_file = shelve.open(pid_tmp_file)
    proc_file["server_port"] = server_port

    """
    Pystray
    """
    if str2bool(cfg_mgr.app_config['put_on_systray']):
        from src.gui.wledtray import WLEDVideoSync_icon

        WLEDVideoSync_icon.run_detached()

    """
    GUI
    """
    # choose GUI
    native_ui = cfg_mgr.app_config['native_ui'] if cfg_mgr.app_config is not None else 'False'
    native_ui_size = cfg_mgr.app_config['native_ui_size'] if cfg_mgr.app_config is not None else '800,600'
    show = None
    try:
        if native_ui.lower() == 'none' or str2bool(cfg_mgr.app_config['put_on_systray']):
            native_ui_size = None
            native_ui = False
            show = False
        elif str2bool(native_ui):
            native_ui = True
            native_ui_size = tuple(native_ui_size.split(','))
            native_ui_size = (int(native_ui_size[0]), int(native_ui_size[1]))
        else:
            show = True
            native_ui_size = None
            native_ui = False
    except Exception as error:
        cfg_mgr.logger.error(f'Error in config file for native_ui : {native_ui} - {error}')
        sys.exit(1)


    """
    RUN
    """
    
    # settings
    app.openapi = CastAPI.custom_openapi
    app.add_static_files('/assets', cfg_mgr.app_root_path('assets'))
    app.add_media_files('/media', cfg_mgr.app_root_path('media'))
    app.add_static_files('/log', cfg_mgr.app_root_path('log'))
    app.add_static_files('/config', cfg_mgr.app_root_path('config'))
    app.add_static_files('/tmp', cfg_mgr.app_root_path('tmp'))
    app.add_static_files('/xtra', cfg_mgr.app_root_path('xtra'))
    app.on_startup(CastAPI.init_actions)

    ui.run(title=f'WLEDVideoSync - {server_port}',
           favicon='favicon.ico',
           host=server_ip,
           port=server_port,
           fastapi_docs=str2bool(cfg_mgr.app_config['fastapi_docs'] if cfg_mgr.app_config is not None else 'True'),
           show=show,
           reconnect_timeout=int(cfg_mgr.server_config['reconnect_timeout'] if cfg_mgr.server_config is not None else '3'),
           reload=False,
           native=native_ui,
           window_size=native_ui_size,
           access_log=False)

    """
    END
    """

    proc_file.close()

    # some cleaning
    Utils.clean_tmp()

    # stop pystray
    if str2bool(cfg_mgr.app_config['put_on_systray']):
        WLEDVideoSync_icon.stop()

    print('End NiceGUI')


def init_linux_win():

    # Apply some default params only once
    # Apply default GUI / param , depend on platform

    if sys.platform.lower() == 'win32':
        Utils.update_ini_key(config_file, 'app', 'preview_proc', 'False')
        Utils.update_ini_key(config_file, 'app', 'native_ui', 'True')
        Utils.update_ini_key(config_file, 'app', 'native_ui_size', '1200,720')
        Utils.update_ini_key(config_file, 'app', 'win_first_run', 'False')

    elif sys.platform.lower() == 'linux':
        # ini settings
        Utils.update_ini_key(config_file, 'app', 'preview_proc', 'True')
        Utils.update_ini_key(config_file, 'app', 'native_ui', 'False')
        Utils.update_ini_key(config_file, 'app', 'native_ui_size', '')
        Utils.update_ini_key(config_file, 'app', 'linux_first_run', 'False')

        # chmod +x info window
        cmd_str = f'chmod +x {cfg_mgr.app_root_path("xtra/info_window")}'
        proc1 = Popen([cmd_str], shell=True, stdin=None, stdout=None, stderr=None)

        # change folder icon
        cmd_str = f'gio set -t string \
        "WLEDVideoSync" metadata::custom-icon file://{cfg_mgr.app_root_path("assets/mac_folder.png")}'
        proc2 = Popen([cmd_str], shell=True, stdin=None, stdout=None, stderr=None)

        # change app icon
        cmd_str = f'gio set -t string \
        "WLEDVideoSync_x86_64.bin" metadata::custom-icon file://{cfg_mgr.app_root_path("favicon.png")}'
        proc3 = Popen([cmd_str], shell=True, stdin=None, stdout=None, stderr=None)

    # common all OS
    init_common()

    def on_ok_click():
        # Close the window when OK button is clicked
        root.destroy()

    # Create the main window
    root = tk.Tk()
    root.title("WLEDVideoSync Information")
    root.geometry("820x460")  # Set the size of the window
    root.configure(bg='#657B83')  # Set the background color

    # Change the window icon
    icon = PhotoImage(file=cfg_mgr.app_root_path('favicon.png'))
    root.iconphoto(False, icon)

    # Define the window's contents
    info_text = ("Extracted executable to WLEDVideoSync folder.....\n\n \
    You can safely delete this file after extraction finished to save some space.\n \
    (the same for WLEDVideoSync.out.txt and err.txt if there ...)\n\n \
    Go to WLEDVideoSync folder and run WLEDVideoSync-{OS} file\n \
    This is a portable version, nothing installed on your system and can be moved where wanted.\n\n \
    Enjoy using WLEDVideoSync\n\n \
    -------------------------------------------------------------------------------------------------\n \
    THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,\n \
    INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n \
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.\n \
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,\n \
    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n \
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n \
    -------------------------------------------------------------------------------------------------\n ")

    info_label = tk.Label(root, text=info_text, bg='#657B83', fg='white', justify=tk.LEFT)
    info_label.pack(padx=10, pady=10)

    # Create the OK button
    ok_button = tk.Button(root, text="Ok", command=on_ok_click, bg='gray', fg='white')
    ok_button.pack(pady=10)

    # Start the Tkinter event loop
    root.mainloop()

    sys.exit()


def init_darwin():
    Utils.update_ini_key(config_file, 'app', 'preview_proc', 'True')
    Utils.update_ini_key(config_file, 'app', 'native_ui', 'False')
    Utils.update_ini_key(config_file, 'app', 'native_ui_size', '')

    # chmod +x info window
    cmd_str = f'chmod +x {cfg_mgr.app_root_path("xtra/info_window")}'
    proc = Popen([cmd_str], shell=True, stdin=None, stdout=None, stderr=None)

    # global
    Utils.update_ini_key(config_file, 'app', 'mac_first_run', 'False')

    # common all OS
    init_common()

    def on_ok_click():
        # Close the window when OK button is clicked
        root.destroy()

    # Create the main window
    root = tk.Tk()
    root.title("WLEDVideoSync Information")
    root.geometry("820x460")  # Set the size of the window
    root.configure(bg='#657B83')  # Set the background color

    # Change the window icon
    icon = PhotoImage(file=cfg_mgr.app_root_path('favicon.png'))
    root.iconphoto(False, icon)

    # Define the window's contents
    info_text = ("Initial settings done for MacOS\n\n"
                 "This is a portable version, nothing installed on your system and can be moved where wanted.\n\n"
                 "Just Re-run it to Enjoy using WLEDVideoSync\n\n \
                 -------------------------------------------------------------------------------------------------\n \
                 THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,\n \
                 INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n \
                 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.\n \
                 IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,\n \
                 DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n \
                 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n \
                 -------------------------------------------------------------------------------------------------\n ")

    info_label = tk.Label(root, text=info_text, bg='#657B83', fg='white', justify=tk.LEFT)
    info_label.pack(padx=10, pady=10)

    # Create the OK button
    ok_button = tk.Button(root, text="Ok", command=on_ok_click, bg='gray', fg='white')
    ok_button.pack(pady=10)

    # Start the Tkinter event loop
    root.mainloop()

    sys.exit()

def init_common():

    # Apply YouTube settings if yt_dlp not imported
    if 'yt_dlp' not in sys.modules:
        Utils.update_ini_key(config_file, 'custom', 'yt-enabled', 'False')

    # global
    Utils.update_ini_key(config_file, 'app', 'init_config_done', 'True')

"""
MAIN Logic 
"""

if __name__ in "__main__":

    config_file = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')

    # test to see if executed from compressed version (linux & win)
    # instruct user to go to WLEDVideoSync folder to execute program (nuitka onefile option) and exit
    if "NUITKA_ONEFILE_PARENT" in os.environ:
        """
        When this env var exist, this mean run from the one-file compressed executable.
        This env not exist when run from the extracted program.
        Expected way to work.
        """
        init_linux_win()

    # On macOS, there is no "NUITKA_ONEFILE_PARENT" so we test on mac_first_run
    # Update necessary params and exit
    if sys.platform.lower() == 'darwin' and str2bool(cfg_mgr.app_config['mac_first_run']):
        init_darwin()


    """
    Start infinite loop
    """

    run_gui()

    """
    STOP
    """

    Utils.clean_tmp()

    cfg_mgr.logger.info('Application Terminated')
