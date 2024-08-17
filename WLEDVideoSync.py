# Compilation mode, standalone everywhere, except on macOS there app bundle
# nuitka-project-if: {OS} in ("Windows", "Linux", "FreeBSD"):
#    nuitka-project: --onefile
# nuitka-project-if: {OS} == "Darwin":
#    nuitka-project: --standalone
#    nuitka-project: --macos-create-app-bundle
# nuitka-project-if: {OS} == "Windows":
#   nuitka-project: --force-stdout-spec=WLEDVideoSync.out.txt
#   nuitka-project: --force-stderr-spec=WLEDVideoSync.err.txt
#    nuitka-project: --onefile-windows-splash-screen-image={MAIN_DIRECTORY}/splash-screen.png
# nuitka-project-if: os.getenv("DEBUG_COMPILATION", "no") == "yes":
#   nuitka-project: --force-stdout-spec=WLEDVideoSync.out.txt
#   nuitka-project: --force-stderr-spec=WLEDVideoSync.err.txt
# nuitka-project: --lto=no
# nuitka-project: --clang

"""
a: zak-45
d : 07/04/2024
v : 1.0.0

Main WLEDVideoSync.

Dispatch all into processes

Webview : provide native OS window
pystray : put on systray if requested

"""

import logging
import logging.config
import concurrent_log_handler

import multiprocessing
from multiprocessing import active_children
import sys
from pathlib import Path as PathLib
import os
import webbrowser

from utils import CASTUtils as Utils

import webview
import webview.menu as wm

from PIL import Image

if sys.platform == 'win32':
    from pystray import Icon, Menu, MenuItem

from uvicorn import Config, Server
from nicegui import native

from str2bool import str2bool

import shelve

"""
When this env var exist, this mean run from the one-file executable (compressed file).
Load of the config is not possible, folder config should not exist.
This avoid FileNotFoundError.
This env not exist when running from the decompressed program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    # read config
    # create logger
    logger = Utils.setup_logging('config/logging.ini', 'WLEDLogger')

    # load config file
    cast_config = Utils.read_config()

    # config keys
    server_config = cast_config[0]  # server key
    app_config = cast_config[1]  # app key
    color_config = cast_config[2]  # colors key
    custom_config = cast_config[3]  # custom key

    #  validate network config
    server_ip = server_config['server_ip']
    if not Utils.validate_ip_address(server_ip):
        logger.error(f'Bad server IP: {server_ip}')
        sys.exit(1)

    server_port = server_config['server_port']

    if server_port == 'auto':
        server_port = native.find_open_port()
    else:
        server_port = int(server_config['server_port'])

    if server_port not in range(1, 65536):
        logger.error(f'Bad server Port: {server_port}')
        sys.exit(2)

    # systray
    put_on_systray = str2bool(app_config['put_on_systray'])

"""
Main test for platform
    MacOS need specific case
    Linux(POSIX) - Windows use the same 
"""
if sys.platform == 'darwin':
    ctx = multiprocessing.get_context('spawn')
    Process = ctx.Process
    Queue = ctx.Queue
else:
    Process = multiprocessing.Process
    Queue = multiprocessing.Queue

"""
Params
"""
#  globals
webview_process = None
instance = None
new_instance = None
main_window = None
netstat_process = None

"""
Uvicorn class    
"""


class UvicornServer(multiprocessing.Process):
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
                                            height=720)

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
    webview.start(menu=menu_items)


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
            logger.warning('Server stopped')
            instance.terminate()
        # if server has been restarted
        if new_instance is not None:
            # get all active child processes
            active_child = active_children()
            # terminate all active children
            # this work here as we have only server instance as child
            for srv_child in active_child:
                srv_child.terminate()
            logger.warning('"Child" Server stopped')

    else:

        logger.info('Server stop Canceled')

    window.destroy()


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
        logger.warning(f'Already running instance : {instance}')
        return
    new_instance = UvicornServer(config=config)
    if not new_instance.is_alive():
        logger.warning('Server restarted')
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

    # test to see if executed from compressed version
    # instruct user to go to WLEDVideoSync folder to execute program
    if "NUITKA_ONEFILE_PARENT" in os.environ:
        import FreeSimpleGUI as sg  # Part 1 - The import

        # Define the window's contents
        info = ("Extracted executable to WLEDVideoSync folder.....\n\n \
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
        layout = [[sg.Text(info)],  # Part 2 - The Layout
                  [sg.Button('Ok')]]
        # Create the window
        window = sg.Window('WLEDVideoSync', layout)  # Part 3 - Window Definition
        # Display and interact with the Window
        event, values = window.read()  # Part 4 - Event loop or Window.read call
        # Finish up by removing from the screen
        window.close()  # Part 5 - Close the Window
        sys.exit()

    """
    Main Params
    """

    show_window = str2bool((app_config['show_window']))

    # store server port info for others processes
    pid = os.getpid()
    tmp_file = f"./tmp/{pid}_file"
    proc_file = shelve.open(tmp_file)
    proc_file["server_port"] = server_port

    """
    Pystray only for Windows 
    """
    if sys.platform.lower() == 'win32':
        # pystray definition
        pystray_image = Image.open('favicon.ico')

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
        Uvicorn

            app : CastAPI.py
            host : 0.0.0.0 for all network interfaces
            port : Bind to a socket with this port
            log_level :  Set the log level. Options: 'critical', 'error', 'warning', 'info', 'debug', 'trace'.
            timeout_graceful_shutdown : After this timeout, the server will start terminating requests

        """
        # uvicorn server definition
        config = Config(app="CastAPI:app",
                        host=server_ip,
                        port=server_port,
                        workers=int(server_config['workers']),
                        log_level=server_config['log_level'],
                        reload=False,
                        timeout_keep_alive=10,
                        timeout_graceful_shutdown=3)

        instance = UvicornServer(config=config)

        """
        START
        """

        # start server
        instance.start()
        logger.info('WLEDVideoSync Started...Server run in separate process')

        # start pywebview process
        # this will start native OS window and block main thread
        if show_window:
            logger.info('Starting webview loop...')
            start_webview_process()
        else:
            start_webview_process('Main')

        # start pystray Icon
        # main infinite loop on systray if requested
        if put_on_systray:
            logger.info('Starting systray loop...')
            WLEDVideoSync_icon.run()

    else:

        # for OS  Linux, Darwin : this will execute ui.run : nicegui main loop
        import CastAPI

    """
    STOP
    """

    # Once Exit option selected from the systray Menu, loop closed ... OR no systray ... continue ...
    proc_file.close()
    logger.info('Remove tmp files')

    try:
        if os.path.isfile(tmp_file + ".dat"):
            os.remove(tmp_file + ".dat")
        if os.path.isfile(tmp_file + ".bak"):
            os.remove(tmp_file + ".bak")
        if os.path.isfile(tmp_file + ".dir"):
            os.remove(tmp_file + ".dir")
        for filename in PathLib("./tmp/").glob("*_file.*"):
            filename.unlink()

        # remove yt files
        if str2bool(app_config['keep_yt']) is not True:
            for filename in PathLib("./media/").glob("yt-tmp-*.*"):
                filename.unlink()
    except Exception as error:
        logger.error(f'Error to remove tmp files : {error}')

    # stop initial server
    logger.info('Stop app')
    if instance is not None:
        instance.stop()
    logger.info('Server is stopped')
    # in case server has been restarted
    if new_instance is not None:
        # get all active child processes (should be only one)
        active_proc = active_children()
        # terminate all active children
        for child in active_proc:
            child.terminate()
        logger.info(f'Active Children: {len(active_proc)} stopped')
    # stop webview if any
    if webview_process is not None:
        logger.info(f'Found webview process...stopping')
        webview_process.terminate()

    logger.info('Application Terminated')
