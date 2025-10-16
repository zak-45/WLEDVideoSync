"""
a: zak-45
d: 07/03/2025
v: 1.0.0.0

Overview
This Python file manages the system tray icon and menu for the WLEDVideoSync application.
It uses the pystray library to create the tray icon and define its associated menu options.
The menu provides quick access to various functionalities of the application, such as opening the main interface,
accessing API documentation, and viewing system information. It also offers the option to open these functionalities in
the default web browser or in a native window using a webview.

Key Components
WLEDVideoSync_systray:
    This is the main object representing the system tray icon. It's initialized with an icon image and a menu.

pystray_menu:
    This Menu object defines the items that appear in the system tray menu.
    Each item is a MenuItem with a label and a callback function.

Callback functions (e.g., on_open_main, on_blackout, on_exit):
    These functions are triggered when the corresponding menu item is clicked.
    They handle actions like opening specific URLs in a web browser or a native webview window,
    controlling WLED devices (e.g., blackout), and exiting the application.

select_win(url, title, width, height):
    This function determines whether to open a given URL in the default web browser or in a native webview window
    based on the native_ui configuration setting.

WebviewManager:
    This class is responsible for managing native webview windows. It's used when the native_ui setting is enabled.

ConfigManager:
    This class manages the application's configuration, including the native_ui setting and other parameters.
    It is used to determine whether to use native windows or the default browser.

server_ip, server_port:
    These variables store the IP address and port number of the WLEDVideoSync server.
    They are used to construct URLs for various application functionalities.

"""


import webbrowser

from PIL import Image
from pystray import Icon, Menu, MenuItem
from src.utl.utils import CASTUtils as Utils
from src.utl.webviewmanager import WebviewManager

from configmanager import cfg_mgr, LoggerManager, NATIVE_UI

logger_manager = LoggerManager(logger_name='WLEDLogger.systray')
systray_logger = logger_manager.logger

server_port = Utils.get_server_port()
server_ip = 'localhost'

WLEDVideoSync_gui = WebviewManager()

def select_win(url, title, width=800, height=600):
    """Open a URL in either a native webview or the default browser.

    Opens the specified URL in a native webview window if native_ui
    is True, otherwise opens it in the default web browser.
    """

    if NATIVE_UI:
        WLEDVideoSync_gui.open_webview(url=url, title=title, width=width, height=height)
    else:
        webbrowser.open(url=url, new=0, autoraise=True)

"""
Pystray menu
"""

def on_open_main():
    """Open the main application interface.

    Opens the main application URL in a native webview window if
    native_ui is True, otherwise opens it in the default browser.
    """
    select_win(f"http://{server_ip}:{server_port}", f'WLEDVideoSync Main Window : {server_port}',
               1200, 720)

def on_open_main_browser():
    """Force open the main application in the default browser.

    Opens the main application URL in the default web browser,
    regardless of the native_ui setting.
    """
    webbrowser.open(f"http://{server_ip}:{server_port}", new=0, autoraise=True)


def on_blackout():
    """
    Stop all casts

    """
    select_win(f"http://{server_ip}:{server_port}/api/util/blackout",f'WLEDVideoSync BLACKOUT : {server_port}',
               400, 150)


def on_player():
    """Open the player interface.

    Opens the player URL in a native webview or the default
    browser, depending on the native_ui setting.
    """

    select_win(f"http://{server_ip}:{server_port}/Player", f'WLEDVideoSync Player: {server_port}',
               1200, 720)

def on_api():
    """
    Open API
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/docs", f'WLEDVideoSync API: {server_port}')

def on_center():
    """
    Open Cast Center
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/Cast-Center", f'WLEDVideoSync Cast Center: {server_port}')

def on_py():
    """
    Open Python Editor
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/Pyeditor", f'WLEDVideoSync Python Editor: {server_port}')

def on_info():
    """
    Menu Info option : show cast information
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/info", f'WLEDVideoSync Infos: {server_port}',
               480, 220)


def on_net():
    """
    Menu Net  option : show charts
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/RunCharts",f'WLEDVideoSync Charts: {server_port}')


def on_details():
    """
    Menu Info Details option : show details cast information
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/DetailsInfo",f'WLEDVideoSync Cast(s) Details: {server_port}')


def on_control_panel():
    """
    Menu control panel option : show control panel
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/control_panel",f'WLEDVideoSync Control Panel: {server_port}',
               width=1200, height=520)


def on_exit():
    """
    Menu Exit option : stop main Loop and continue
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/ShutDown",f'WLEDVideoSync SHUTDOWN: {server_port}',
               width=380, height=50)


"""
Pystray definition
"""

pystray_image = Image.open(cfg_mgr.app_root_path('favicon.ico'))

pystray_menu = Menu(
    MenuItem('Open', on_open_main, visible=True,default=True),
    MenuItem('Open in Browser: Force', on_open_main_browser),
    Menu.SEPARATOR,
    MenuItem('BLACKOUT', on_blackout),
    Menu.SEPARATOR,
    MenuItem('Player', on_player),
    MenuItem('Control Panel', on_control_panel),
    Menu.SEPARATOR,
    MenuItem('API', on_api),
    Menu.SEPARATOR,
    MenuItem('Center', on_center),
    Menu.SEPARATOR,
    MenuItem('Cast details', on_details),
    MenuItem('Info', on_info),
    MenuItem('Charts', on_net),
    MenuItem('PyEditor', on_py),
    Menu.SEPARATOR,
    MenuItem(f'Exit - server :  {server_port}', on_exit)
)

WLEDVideoSync_systray = Icon('WLEDVideoSync', icon=pystray_image, menu=pystray_menu)

# example use
if __name__ == "__main__":
    import time

    WLEDVideoSync_systray.run_detached()
    print('look on systray, this will shutdown in 10s...')
    while True:
        time.sleep(10)
        break
    WLEDVideoSync_systray.stop()
    print('end  of systray')



