from PIL import Image
from pystray import Icon, Menu, MenuItem
import webbrowser
from src.utl.utils import CASTUtils as Utils

from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger')

server_port = Utils.get_server_port()
server_ip = 'localhost'

"""
Pystray menu
"""

def on_open_bro():
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
    webbrowser.open(f"http://{server_ip}:{server_port}/api/util/blackout",new=1,autoraise=True)


def on_player():
    """
    Open video Player
    :return:
    """
    webbrowser.open(f"http://{server_ip}:{server_port}/Player", new=0, autoraise=True)

def on_info():
    """
    Menu Info option : show cast information in native OS Window
    :return:
    """
    webbrowser.open(f"http://{server_ip}:{server_port}/info", new=0, autoraise=True)


def on_net():
    """
    Menu Net  option : show Network bandwidth utilization
    :return:
    """
    webbrowser.open(f"http://{server_ip}:{server_port}/RunCharts", new=0, autoraise=True)


def on_details():
    """
    Menu Info Details option : show details cast information in native OS Window
    :return:
    """
    webbrowser.open(f"http://{server_ip}:{server_port}/DetailsInfo", new=0, autoraise=True)


def on_exit():
    """
    Menu Exit option : stop main Loop and continue
    :return:
    """
    webbrowser.open(f"http://{server_ip}:{server_port}/ShutDown", new=0, autoraise=True)


"""
Pystray definition
"""

pystray_image = Image.open(cfg_mgr.app_root_path('favicon.ico'))

pystray_menu = Menu(
    MenuItem('Open in Browser', on_open_bro),
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
