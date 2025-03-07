from PIL import Image
from pystray import Icon, Menu, MenuItem
import webbrowser

from str2bool import str2bool

from src.utl.utils import CASTUtils as Utils
from src.gui.webviewmanager import WebviewManager

from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger')

server_port = Utils.get_server_port()
server_ip = 'localhost'

WLEDVideoSync_gui = WebviewManager()
native_ui = str2bool(cfg_mgr.app_config['systray_native']) if cfg_mgr.app_config is not None else False

def select_win(url, title, width=800, height=600):

    if native_ui:
        WLEDVideoSync_gui.open_webview(url=url, title=title, width=width, height=height)
    else:
        webbrowser.open(url=url, new=0, autoraise=True)

"""
Pystray menu
"""

def on_open_main():
    """
    Menu Open Browser option : show GUI app in default browser
    :return:
    """

    select_win(f"http://{server_ip}:{server_port}", 'Main Window', 1200, 720)

def on_open_main_bro():
    """
    Menu Open Browser option : show GUI app in default browser
    :return:
    """

    webbrowser.open(f"http://{server_ip}:{server_port}", new=0, autoraise=True)


def on_blackout():
    """
    Put all WLED DDP devices to Off : show in native OS Window
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/api/util/blackout",'BLACKOUT', 400, 150)


def on_player():
    """
    Open video Player
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/Player", 'Player', 1200, 720)

def on_api():
    """
    Open API
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/docs", 'API')

def on_py():
    """
    Open Python Editor
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/Pyeditor", 'Python Editor')

def on_info():
    """
    Menu Info option : show cast information in native OS Window
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/info", 'Infos', 480, 220)


def on_net():
    """
    Menu Net  option : show Network bandwidth utilization
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/RunCharts",'Charts')


def on_details():
    """
    Menu Info Details option : show details cast information in native OS Window
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/DetailsInfo",'Cast(s) Details')


def on_exit():
    """
    Menu Exit option : stop main Loop and continue
    :return:
    """
    select_win(f"http://{server_ip}:{server_port}/ShutDown",'SHUTDOWN', 100, 50)
    # native_gui.close_all_webviews()


"""
Pystray definition
"""

pystray_image = Image.open(cfg_mgr.app_root_path('favicon.ico'))

pystray_menu = Menu(
    MenuItem('Open', on_open_main, visible=True,default=True),
    MenuItem('Open in Browser: Force', on_open_main_bro),
    Menu.SEPARATOR,
    MenuItem('BLACKOUT', on_blackout),
    Menu.SEPARATOR,
    MenuItem('Player', on_player),
    Menu.SEPARATOR,
    MenuItem('API', on_api),
    Menu.SEPARATOR,
    MenuItem('Cast details', on_details),
    MenuItem('Info', on_info),
    MenuItem('Charts', on_net),
    MenuItem('PyEditor', on_py),
    Menu.SEPARATOR,
    MenuItem(f'Exit - server :  {server_port}', on_exit)
)

WLEDVideoSync_systray = Icon('WLEDVideoSync', icon=pystray_image, menu=pystray_menu)


if __name__ in "__main__":

    native_view = WebviewManager()
    native_view.open_webview('https://example.com', 'Example Window', 800, 600)

