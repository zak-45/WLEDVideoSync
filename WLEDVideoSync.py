"""
a: zak-45
d : 07/04/2024
v : 1.0.0

Main WLEDVideoSync

Dispatch all into processes

Webview : provide native OS window
pystray : put on systray if requested

Nuitka compilation :
nuitka WLEDVideoSync.py
--standalone
--follow-imports
--include-module=CastAPI
--include-module=pygments.formatters.html
--include-module=zeroconf._utils.ipaddress
--include-module=zeroconf._handlers.answers
--disable-console
--force-stdout-spec=log/WLEDVideoSync_stdout.txt
--force-stderr-spec=log/WLEDVideoSync_stderr.txt

and need nicegui files
python -m nuitka --follow-imports --include-plugin-directory=plugin_dir program.py
--windows-disable-console
--windows-force-stdout-spec = ./static/log/build.out.txt
--windows-force-stderr-spec = ./static/log/build.err.txt
copier favicon.ico
copier assets et media

"""

import logging
import logging.config

import multiprocessing
from multiprocessing import active_children
import sys
import time
import webbrowser

from utils import CASTUtils as Utils, LogElementHandler

import webview
import webview.menu as wm

from PIL import Image
from pystray import Icon, Menu, MenuItem

from uvicorn import Config, Server

import cfg_load as cfg
from str2bool import str2bool

# read config
logging.config.fileConfig('config/logging.ini')
# create logger
logger = logging.getLogger('WLEDLogger')

# load config file
cast_config = cfg.load('config/WLEDVideoSync.ini')

# config keys
server_config = cast_config.get('server')
app_config = cast_config.get('app')

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
new_instance = None
main_window = None

#  validate network config
server_ip = server_config['server_ip']
if not Utils.validate_ip_address(server_ip):
    print(f'Bad server IP: {server_ip}')
    sys.exit(1)
server_port = int(server_config['server_port'])
if server_port not in range(1, 65536):
    print(f'Bad server Port: {server_port}')
    sys.exit(2)

# systray
put_on_systray = str2bool(app_config['put_on_systray'])

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


def run_webview(window_name):
    """
    create window
    :return:
    """
    global main_window

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
    if window_name == 'Main':
        # Main window : splash screen
        main_window = webview.create_window(title='WLEDVideoSync',
                                            url=f'http://127.0.0.1:{server_port}/WLEDVideoSync')

    elif window_name == 'Info':
        # Info window : cast
        main_window = webview.create_window(
            title='Cast Info',
            url=f"http://{server_ip}:{server_port}/info",
            width=460,
            height=240
        )

    elif window_name == 'StopSrv':
        # Stop server window with confirmation
        main_window = webview.create_window(
            title='Confirmation dialog',
            html='<p>Confirmation</p>',
            hidden=True
        )

    elif window_name == 'BlackOut':
        # Blackout window : show result from api blackout
        main_window = webview.create_window(
            title='BLACKOUT',
            url=f"http://{server_ip}:{server_port}/api/util/blackout",
            width=300,
            height=150
        )

    elif window_name == 'Details':
        # info details window : show result from api CastInfo
        main_window = webview.create_window(
            title='Casts Details',
            url=f"http://{server_ip}:{server_port}/DetailsInfo",
            width=640,
            height=480
        )

    # start webview, dialog or not
    if window_name == 'StopSrv':
        webview.start(dialog_stop_server, main_window)
    else:
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
        main_window.load_url(f'http://127.0.0.1:{server_port}/WLEDVideoSync')


def dialog_stop_server(window):
    """
    Dialog window: true stop server
    :param window:
    :return:
    """
    result = window.create_confirmation_dialog('Confirmation', 'Do you really want to stop the Server?')
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
            logger.warning('Server stopped')

    else:

        logger.info('Server stop Canceled')

    window.destroy()
    time.sleep(2)


"""
MAIN Logic 
"""

if __name__ == '__main__':

    multiprocessing.freeze_support()

    """
    Main Params
    """

    show_window = str2bool((app_config['show_window']))

    """
    Pywebview
    """


    def start_webview_process(window_name='Main'):
        """
        start a pywebview process and call a window
        :return:
        """
        global webview_process
        webview_process = Process(target=run_webview(window_name))
        webview_process.daemon = True
        webview_process.start()


    """
    Pystray 
    """


    def on_open():
        """
        Menu Open option : show GUI app in native OS Window
        :return:
        """
        global webview_process
        if webview_process is None:
            start_webview_process()
        else:
            if not webview_process.is_alive():
                start_webview_process()


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
        global webview_process
        if webview_process is None:
            start_webview_process('StopSrv')
        else:
            if not webview_process.is_alive():
                start_webview_process('StopSrv')


    def on_restart_srv():
        """
        Menu restart  server option
        :return:
        """
        global new_instance
        if instance.is_alive():
            return
        new_instance = UvicornServer(config=config)
        if not new_instance.is_alive():
            logger.warning('Server restarted')
            new_instance.start()

        time.sleep(2)


    def on_blackout():
        """
        Put all WLED DDP devices to Off : show in native OS Window
        :return:
        """
        global webview_process
        if webview_process is None:
            start_webview_process('BlackOut')
        else:
            if not webview_process.is_alive():
                start_webview_process('BlackOut')


    def on_info():
        """
        Menu Info option : show cast information in native OS Window
        :return:
        """

        global webview_process
        if webview_process is None:
            start_webview_process('Info')
        else:
            if not webview_process.is_alive():
                start_webview_process('Info')

    def on_details():
        """
        Menu Info Details option : show details cast information in native OS Window
        :return:
        """

        global webview_process
        if webview_process is None:
            start_webview_process('Details')
        else:
            if not webview_process.is_alive():
                start_webview_process('Details')


    def on_exit():
        """
        Menu Exit option : stop main Loop and continue
        :return:
        """
        WLEDVideoSync_icon.stop()


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
        MenuItem('Info', on_info),
        MenuItem('Info details', on_details),
        Menu.SEPARATOR,
        MenuItem('Exit', on_exit)
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
                    timeout_graceful_shutdown=1)

    instance = UvicornServer(config=config)

    """
    START
    """

    # start server
    logger.info('WLEDVideoSync Starting...')
    instance.start()

    # start pywebview process
    # this will start native OS window and block main thread
    if show_window:
        start_webview_process()

    # start pystray Icon
    # main infinite loop on systray if requested
    if put_on_systray:
        WLEDVideoSync_icon.run()

    """
    STOP
    """
    # Once Exit option selected from the systray Menu loop closed ... OR no systray ... continue ...
    logger.info('stop app')
    # stop initial server
    instance.stop()
    logger.info('Server is stopped')
    # in case server has been restarted
    if new_instance is not None:
        # get all active child processes (should be only one)
        active_proc = active_children()
        logger.info(f'Active Children: {len(active_proc)} stopped')
        # terminate all active children
        for child in active_proc:
            child.terminate()
    # stop webview if any
    if webview_process is not None:
        webview_process.terminate()

    logger.info('Application Terminated')
