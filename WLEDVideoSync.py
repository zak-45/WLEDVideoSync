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

Dispatch all into processes

Webview : provide native OS window
pystray : put on systray if requested

Nuitka Project Configuration
The script defines different compilation modes based on the operating system and some environment variables:

General Compilation Mode:

For Windows, Linux, and FreeBSD: --onefile mode.
For macOS (Darwin): --standalone mode with an app bundle creation.
Windows Specific Configuration:

Adds a custom splash screen for the executable.
Debug and Feature Flags:

If DEBUG_COMPILATION environment variable is set to "yes", output is redirected to specific files.
If YOUTUBE_DISABLE is set, certain modules related to YouTube are excluded from the import.
If YOUTUBE_DISABLE is not set, includes specific deprecated YouTube utilities.
Linux Specific Configuration:

Includes modules for GTK and Qt (graphical interfaces).
General Exclusions and Error Handling:
Excludes the doctest module.

Sets a default error mode for missing includes.

Main Application Logic:

Handles different processes for web view, server management, and system tray functionality using pywebview and pystray.
Uvicorn Server Management:

Defines a class for managing an Uvicorn server instance (used for running ASGI applications).
Webview Windows:

Functions for creating and managing different windows using pywebview.
System Tray (Windows Only):

Defines system tray icons and menu items for various functionalities like opening the application, stopping the server,
and accessing information.
Main Execution Block:

Handles different behaviors based on whether the script is run as a standalone executable or not.

Starts the Uvicorn server and manages webview and system tray interactions.
Cleans up temporary files and stops the server gracefully on exit.

Key Functionalities
Conditional Compilation: The script uses conditions to set different compilation modes and options based
on the operating system and environment variables.

Multiprocessing Setup: Utilizes Python's multiprocessing library to manage different processes for the application.

Server Configuration: Configures and manages an Uvicorn server for hosting the application's backend.

Webview Integration: Uses pywebview to provide a native OS window for the application's web interface.

System Tray: Implements a system tray icon with menu options to manage the application on Windows.

"""
import sys
import shelve
import webview
import webview.menu as wm
import os
import webbrowser
import tkinter as tk

from tkinter import PhotoImage
from src.utl.utils import CASTUtils as Utils
from pathlib import Path as PathLib
from multiprocessing import active_children
from PIL import Image
from uvicorn import Config, Server
from nicegui import native
from str2bool import str2bool
from pystray import Icon, Menu, MenuItem
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger')

Process, Queue = Utils.mp_setup()

"""
When this env var exist, this mean run from the one-file executable (compressed file).
This env not exist when running from the decompressed program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:

    #  validate network config
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

    # systray
    put_on_systray = str2bool(cfg_mgr.app_config['put_on_systray'])


"""
Params
"""
#
webview_process = None
instance = None
new_instance = None
main_window = None
netstat_process = None

"""
Uvicorn class    
"""

class UvicornServer(Process):
    """
    This allows to do stop / run server and define programmatically Config
    """

    def __init__(self, config: Config):
        super().__init__()
        self.server = Server(config=config)
        self.config = config

    def stop(self):
        self.server.should_exit = True
        self.server.force_exit = True
        self.terminate()

    def run(self, *args, **kwargs):
        self.server.run()

"""
Webview : local OS native Window
"""
"""
Pywebview
"""

def start_webview_process(window_name='Splash'):
    """
    start a pywebview process and call a window
    :return:
    """
    global webview_process, main_window
    """
    webview_process = Process(target=run_webview, args=(window_name,))
    webview_process.daemon = True
    webview_process.start()
    """
    # start in blocking mode

    # destroy if exist
    if main_window is not None:
        main_window.destroy()

    # Menu Items definition
    if window_name in ['StopSrv', 'Info', 'BlackOut', 'Details']:
        # minimalist Menu
        menu_items = [
            wm.Menu('Options',
                    [wm.MenuAction('Exit on SysTray', keep_running)]
                    )
        ]
    else:
        # Main menu
        menu_items = [wm.Menu('Main',
                              [wm.MenuAction('HOME Screen', go_to_home)]
                              ),
                      wm.Menu('Options',
                              [wm.MenuAction('Keep it running (Put to SysTray)', keep_running)]
                              )
                      ]

    # Window creation
    if window_name == 'Splash':
        # Main window : splash screen
        main_window = webview.create_window(title=f'WLEDVideoSync {server_port}',
                                            url=f'http://{server_ip}:{server_port}/WLEDVideoSync',
                                            width=1200,
                                            height=720)

    elif window_name == 'Main':
        # Main window : splash screen
        main_window = webview.create_window(title=f'MAIN WLEDVideoSync {server_port}',
                                            url=f'http://{server_ip}:{server_port}',
                                            width=1200,
                                            height=720, text_select=False)

    elif window_name == 'Info':
        # Info window : cast
        main_window = webview.create_window(
            title=f'Cast Info {server_port}',
            url=f"http://{server_ip}:{server_port}/info",
            width=540,
            height=230
        )

    elif window_name == 'BlackOut':
        # Blackout window : show result from api blackout
        if main_window is not None:
            main_window.destroy()
        main_window = webview.create_window(
            title=f'BLACKOUT {server_port}',
            url=f"http://{server_ip}:{server_port}/api/util/blackout",
            width=300,
            height=150
        )

    elif window_name == 'Details':
        # info details and manage window : show result from api CastManage
        if main_window is not None:
            main_window.destroy()
        main_window = webview.create_window(
            title=f'Casts Details {server_port}',
            url=f"http://{server_ip}:{server_port}/DetailsInfo",
            width=640,
            height=480
        )

    elif window_name == 'Player':
        # Run video player
        if main_window is not None:
            main_window.destroy()
        main_window = webview.create_window(
            title=f'Video Player {server_port}',
            url=f"http://{server_ip}:{server_port}/Player",
            width=800,
            height=600
        )

    elif window_name == 'Charts':
        # Page to select charts
        if main_window is not None:
            main_window.destroy()
        main_window = webview.create_window(
            title=f'Run Charts {server_port}',
            url=f"http://{server_ip}:{server_port}/RunCharts",
            width=450,
            height=180
        )

    # start webview
    # To change a default renderer set PYWEBVIEW_GUI environment variable: cef, qt, gtk ...
    webview.start(menu=menu_items, debug=False)


def keep_running():
    """
    Menu option
    :return:
    """
    global put_on_systray

    put_on_systray = True
    if main_window is not None:
        main_window.destroy()


def go_to_home():
    """
    Menu option
    :return:
    """
    if main_window is not None:
        main_window.load_url(f'http://{server_ip}:{server_port}/WLEDVideoSync')


def dialog_stop_server(my_window):
    """
    Dialog window: true stop server
    :param my_window:
    :return:
    """
    result = my_window.create_confirmation_dialog(f'Confirm-{server_port}', 'Do you really want to stop the Server?')
    if result:
        # initial instance
        if instance.is_alive():
            cfg_mgr.logger.warning('Server stopped')
            instance.terminate()
        # if server has been restarted
        if new_instance is not None:
            # get all active child processes
            active_child = active_children()
            # terminate all active children
            # this work here as we have only server instance as child
            for srv_child in active_child:
                srv_child.terminate()
            cfg_mgr.logger.warning('"Child" Server stopped')

    else:

        cfg_mgr.logger.debug('Server stop Canceled')

    my_window.destroy()


"""
Pystray
"""


def on_open():
    """
    Menu Open option : show GUI app in native OS Window
    :return:
    """
    global webview_process
    if webview_process is not None:
        webview_process.terminate()
    start_webview_process('Main')


def on_open_bro():
    """
    Menu Open Browser option : show GUI app in default browser
    :return:
    """
    webbrowser.open(f"http://{server_ip}:{server_port}", new=0, autoraise=True)


def on_stop_srv():
    """
    Menu Stop  server option : show in native OS Window
    :return:
    """
    stop_window = webview.create_window(
        title='Confirmation dialog',
        html=f'<p>Confirmation</p>',
        hidden=True
    )
    webview.start(dialog_stop_server, stop_window)


def on_restart_srv():
    """
    Menu restart  server option
    :return:
    """
    global new_instance

    if instance.is_alive():
        cfg_mgr.logger.warning(f'Already running instance : {instance}')
        return
    new_instance = UvicornServer(config=u_config)
    if not new_instance.is_alive():
        cfg_mgr.logger.warning('Server restarted')
        new_instance.start()


def on_blackout():
    """
    Put all WLED DDP devices to Off : show in native OS Window
    :return:
    """
    global webview_process
    if webview_process is not None:
        webview_process.terminate()
    start_webview_process('BlackOut')


def on_player():
    """
    Open video Player
    :return:
    """
    global webview_process
    if webview_process is not None:
        webview_process.terminate()
    start_webview_process('Player')


def on_info():
    """
    Menu Info option : show cast information in native OS Window
    :return:
    """
    global webview_process
    if webview_process is not None:
        webview_process.terminate()
    start_webview_process('Info')


def on_net():
    """
    Menu Net  option : show Network bandwidth utilization
    :return:
    """
    global webview_process
    if webview_process is not None:
        webview_process.terminate()
    start_webview_process('Charts')


def on_details():
    """
    Menu Info Details option : show details cast information in native OS Window
    :return:
    """
    global webview_process
    if webview_process is not None:
        webview_process.terminate()
    start_webview_process('Details')


def on_exit():
    """
    Menu Exit option : stop main Loop and continue
    :return:
    """
    global webview_process
    if main_window is not None:
        main_window.destroy()
    if webview_process is not None:
        webview_process.terminate()
    WLEDVideoSync_icon.stop()


"""
MAIN Logic 
"""

if __name__ == '__main__':
    # packaging support (compile)
    from multiprocessing import freeze_support  # noqa

    freeze_support()  # noqa

    config_file = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')

    # test to see if executed from compressed version
    # instruct user to go to WLEDVideoSync folder to execute program (nuitka onefile option)
    if "NUITKA_ONEFILE_PARENT" in os.environ:

        config_file = cfg_mgr.app_root_path('WLEDVideoSync/config/WLEDVideoSync.ini')

        # Apply some default params only once
        # Apply default GUI / param , depend on platform

        if sys.platform.lower() == 'win32':
            Utils.update_ini_key(config_file, 'app', 'preview_proc', 'False')
            Utils.update_ini_key(config_file, 'app', 'native_ui', 'True')
            Utils.update_ini_key(config_file, 'app', 'native_ui_size', '1200,720')
            Utils.update_ini_key(config_file, 'app', 'uvicorn', 'True')
        else:
            Utils.update_ini_key(config_file, 'app', 'preview_proc', 'True')
            Utils.update_ini_key(config_file, 'app', 'native_ui', 'False')
            Utils.update_ini_key(config_file, 'app', 'native_ui_size', '')
            Utils.update_ini_key(config_file, 'app', 'uvicorn', 'False')

        # Apply YouTube settings if yt_dlp not imported
        if 'yt_dlp' not in sys.modules:
            Utils.update_ini_key(config_file, 'custom', 'yt-enable', 'False')

        # global
        Utils.update_ini_key(config_file, 'app', 'init_config_done', 'True')

        def on_ok_click():
            # Close the window when OK button is clicked
            root.destroy()

        # Create the main window
        root = tk.Tk()
        root.title("WLEDVideoSync Information")
        root.geometry("820x460")  # Set the size of the window
        root.configure(bg='#657B83')  # Set the background color

        # Change the window icon
        icon = PhotoImage(file=cfg_mgr.app_root_path('WLEDVideoSync/favicon.png'))
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

    elif sys.platform.lower() == 'darwin' and str2bool(cfg_mgr.app_config['mac_first_run']):

        Utils.update_ini_key(config_file, 'app', 'preview_proc', 'True')
        Utils.update_ini_key(config_file, 'app', 'native_ui', 'False')
        Utils.update_ini_key(config_file, 'app', 'native_ui_size', '')
        Utils.update_ini_key(config_file, 'app', 'uvicorn', 'False')

        # Apply YouTube settings if yt_dlp not imported
        if 'yt_dlp' not in sys.modules:
            Utils.update_ini_key(config_file, 'custom', 'yt-enable', 'False')

        # global
        Utils.update_ini_key(config_file, 'app', 'init_config_done', 'True')
        # global
        Utils.update_ini_key(config_file, 'app', 'mac_first_run', 'False')

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

    """
    Main Params
    """

    show_window = str2bool((cfg_mgr.app_config['show_window']))

    # store server port info for others processes
    pid = os.getpid()

    pid_tmp_file = cfg_mgr.app_root_path(f"tmp/{pid}_file")
    proc_file = shelve.open(pid_tmp_file)
    proc_file["server_port"] = server_port

    """
    Pystray definition
    """

    # pystray definition
    favicon_file=cfg_mgr.app_root_path('favicon.ico')
    pystray_image = Image.open(favicon_file)

    pystray_menu = Menu(
        MenuItem('Open', on_open),
        MenuItem('Open in Browser', on_open_bro),
        Menu.SEPARATOR,
        MenuItem('Stop server', on_stop_srv),
        MenuItem('ReStart server', on_restart_srv),
        Menu.SEPARATOR,
        MenuItem('BLACKOUT', on_blackout),
        Menu.SEPARATOR,
        MenuItem('Player', on_player),
        Menu.SEPARATOR,
        MenuItem('Cast details', on_details),
        MenuItem('Info', on_info),
        MenuItem('Charts', on_net),
        Menu.SEPARATOR,
        MenuItem(f'Exit - server :  {server_port}', on_exit)
    )

    WLEDVideoSync_icon = Icon('Pystray', pystray_image, menu=pystray_menu)

    """
    Run uvicorn server 
    """

    if str2bool(cfg_mgr.app_config['uvicorn']) is True:
        """
        Uvicorn

            app : CastAPI.py
            host : 0.0.0.0 for all network interfaces
            port : Bind to a socket with this port
            log_level :  Set the log level. Options: 'critical', 'error', 'warning', 'info', 'debug', 'trace'.
            timeout_graceful_shutdown : After this timeout, the server will start terminating requests

        """
        # uvicorn server definition
        u_config = Config(app="CastAPI:app",
                        host=server_ip,
                        port=server_port,
                        workers=int(cfg_mgr.server_config['workers']),
                        log_level=cfg_mgr.server_config['log_level'],
                        access_log=False,
                        reload=False,
                        timeout_keep_alive=10,
                        timeout_graceful_shutdown=3)

        instance = UvicornServer(config=u_config)

        """
        START
        """

        # start server
        instance.start()
        cfg_mgr.logger.debug('WLEDVideoSync Started...Server run in separate process')

        """
        systray and webview only if OS win32
        """

        if sys.platform.lower() == 'win32':

            # start pywebview process
            # this will start native OS window and block main thread
            if show_window:
                cfg_mgr.logger.debug('Starting webview loop...')
                start_webview_process()
            else:
                start_webview_process('Main')

            # start pystray Icon
            # main infinite loop on systray if requested
            if put_on_systray:
                cfg_mgr.logger.debug('Starting systray loop...')
                WLEDVideoSync_icon.run()

    else:

        # run NiceGUI app with built-in server
        import CastAPI

    """
    STOP
    """

    # Once Exit option selected from the systray Menu, loop closed ... OR no systray ... continue ...
    proc_file.close()
    cfg_mgr.logger.debug('Remove tmp files')

    try:
        if os.path.isfile(pid_tmp_file + ".dat"):
            os.remove(pid_tmp_file + ".dat")
        if os.path.isfile(pid_tmp_file + ".bak"):
            os.remove(pid_tmp_file + ".bak")
        if os.path.isfile(pid_tmp_file + ".dir"):
            os.remove(pid_tmp_file + ".dir")

        for filename in PathLib("./tmp/").glob("*_file.*"):
            filename.unlink()

        # remove yt files
        if str2bool(cfg_mgr.app_config['keep_yt']) is not True:
            for filename in PathLib("./media/").glob("yt-tmp-*.*"):
                filename.unlink()
        # remove image files
        if str2bool(cfg_mgr.app_config['keep_image']) is not True:
            for filename in PathLib("./media/").glob("image_*_*.jpg"):
                filename.unlink()

    except Exception as error:
        cfg_mgr.logger.error(f'Error to remove tmp files : {error}')

    # stop initial server
    cfg_mgr.logger.info('Stop app')
    if instance is not None:
        instance.stop()
    cfg_mgr.logger.info('Server is stopped')
    # in case server has been restarted
    if new_instance is not None:
        # get all active child processes (should be only one)
        active_proc = active_children()
        # terminate all active children
        for child in active_proc:
            child.terminate()
        cfg_mgr.logger.info(f'Active Children: {len(active_proc)} stopped')
    # stop webview if any
    if webview_process is not None:
        cfg_mgr.logger.info(f'Found webview process...stopping')
        webview_process.terminate()

    cfg_mgr.logger.info('Application Terminated')
