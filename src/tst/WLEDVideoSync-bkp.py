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

Webview Windows:

Functions for creating and managing different windows using pywebview.
System Tray (Windows Only):

Defines system tray icons and menu items for various functionalities like opening the application, stopping the server,
and accessing information.
Main Execution Block:

Handles different behaviors based on whether the script is run as a standalone executable or not.

Manages webview and system tray interactions.
Cleans up temporary files and stops the server gracefully on exit.

Key Functionalities
Conditional Compilation: The script uses conditions to set different compilation modes and options based
on the operating system and environment variables.

Multiprocessing Setup: Utilizes Python's multiprocessing library to manage different processes for the application.

Webview Integration: Uses pywebview to provide a native OS window for the application's web interface.

System Tray: Implements a system tray icon with menu options to manage the application on Windows.

"""
import signal
import sys
import shelve
from subprocess import Popen

from nicegui import ui, app , native

import webview
import webview.menu as wm
import os
import webbrowser
import tkinter as tk
import CastAPI

from tkinter import PhotoImage
from src.utl.utils import CASTUtils as Utils
from PIL import Image
from str2bool import str2bool
from configmanager import ConfigManager

if sys.platform.lower() == 'win32':
    from pystray import Icon, Menu, MenuItem

cfg_mgr = ConfigManager(logger_name='WLEDLogger')

Process, Queue = Utils.mp_setup()

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

    """
    A None value indicates that the process hasn't terminated yet.
    """

    result = my_window.create_confirmation_dialog(f'Confirm-{server_port}', 'Do you really want to stop the Server?')

    if result and server_is_alive(server_proc):
        os.kill(server_proc.pid, signal.SIGTERM)
        cfg_mgr.logger.warning('Server stopped')

    elif not server_is_alive(server_proc):
        cfg_mgr.logger.error('No Running Server')

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
    global server_proc

    if not server_is_alive(server_proc):
        # Run CastAPI into its own process
        server_proc = Popen([sys.executable, "-m", "CastAPI"])
        cfg_mgr.logger.info(f'WLEDVideoSync Started...Server run in separate process {server_proc.pid}')
    else:
        cfg_mgr.logger.error(f'Server already run in separate process {server_proc.pid}')

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


def server_is_alive(i_proc):
    return True if  i_proc.poll() is None else False



def run_gui():
    log_ui = None
    server_port = None
    server_ip = None

    print('start NiceGui')

    """
    When this env var exist, this mean run from the one-file compressed executable.
    This env not exist when run from the extracted program.
    Expected way to work.
    """
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

    # choose GUI
    native_ui = cfg_mgr.app_config['native_ui'] if cfg_mgr.app_config is not None else 'False'
    native_ui_size = cfg_mgr.app_config['native_ui_size'] if cfg_mgr.app_config is not None else '800,600'
    show = None
    try:
        if native_ui.lower() == 'none' or (str2bool(native_ui) and sys.platform.lower() == 'win32'):
            native_ui_size = None
            native_ui = False
            show = False
        elif str2bool(native_ui) and sys.platform.lower() != 'win32':
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

    ui.run(title='WLEDVideoSync',
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
    # some cleaning
    Utils.clean_tmp()

    print('End NiceGUI')


"""
MAIN Logic 
"""

if __name__ in "__main__":
    # packaging support (compile)
    from multiprocessing import freeze_support  # noqa
    freeze_support()  # noqa

    """
    Params
    """
    #
    webview_process = None
    main_window = None

    config_file = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')

    # test to see if executed from compressed version
    # instruct user to go to WLEDVideoSync folder to execute program (nuitka onefile option)
    if "NUITKA_ONEFILE_PARENT" in os.environ:

        config_file = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')

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


        # Apply YouTube settings if yt_dlp not imported
        if 'yt_dlp' not in sys.modules:
            Utils.update_ini_key(config_file, 'custom', 'yt-enabled', 'False')

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

    else:

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

    if sys.platform.lower() == 'darwin' and str2bool(cfg_mgr.app_config['mac_first_run']):

        Utils.update_ini_key(config_file, 'app', 'preview_proc', 'True')
        Utils.update_ini_key(config_file, 'app', 'native_ui', 'False')
        Utils.update_ini_key(config_file, 'app', 'native_ui_size', '')


        # chmod +x info window
        cmd_str = f'chmod +x {cfg_mgr.app_root_path("xtra/info_window")}'
        proc = Popen([cmd_str], shell=True, stdin=None, stdout=None, stderr=None)

        # Apply YouTube settings if yt_dlp not imported
        if 'yt_dlp' not in sys.modules:
            Utils.update_ini_key(config_file, 'custom', 'yt-enabled', 'False')

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
    server_proc = None
    show_window = str2bool((cfg_mgr.app_config['show_window']))

    # store server port info for others processes
    pid = os.getpid()

    pid_tmp_file = cfg_mgr.app_root_path(f"tmp/{pid}_file")
    proc_file = shelve.open(pid_tmp_file)
    proc_file["server_port"] = server_port

    """
    Pystray definition
    """

    if sys.platform.lower() == 'win32':
        # pystray definition
        pystray_image = Image.open(cfg_mgr.app_root_path('favicon.ico'))

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

        WLEDVideoSync_icon = Icon('Pystray', icon=pystray_image, menu=pystray_menu)

        """
        START
        """

        # Run CastAPI into its own process
        # server_proc = Popen([sys.executable, "-m", "CastAPI"])
        #server_proc = Process(target=run_gui)
        #server_proc.start()
        #server_proc.join()
        run_gui()

        # cfg_mgr.logger.debug(f'WLEDVideoSync Started...Server run in separate process {server_proc.pid}')

        """
        systray and webview only if OS win32
        """
        if sys.platform.lower() == 'win32' and str2bool(cfg_mgr.app_config['native_ui']):

            # start pywebview process
            # this will start native OS window and block main thread
            cfg_mgr.logger.debug('Starting webview loop...')
            if show_window:
                start_webview_process()
            else:
                start_webview_process('Main')

            # start pystray Icon
            # main infinite loop on systray if requested
            if put_on_systray:
                cfg_mgr.logger.debug('Starting systray loop...')
                WLEDVideoSync_icon.run()

        else:

            server_proc.wait()


    # Once Exit option selected from the systray Menu, loop closed ... OR no systray ... continue ...
    """
    STOP
    """
    if server_is_alive(server_proc):
        os.kill(server_proc.pid, signal.SIGTERM)

    proc_file.close()

    Utils.clean_tmp()

    # stop webview if any
    if webview_process is not None:
        cfg_mgr.logger.info(f'Found webview process...stopping')
        webview_process.terminate()

    cfg_mgr.logger.info('Application Terminated')
