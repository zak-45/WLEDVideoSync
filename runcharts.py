"""
a: zak-45
d: 10/03/2025
v: 1.0.0

This script provides a launcher UI for the various system and device monitoring charts.
It presents a simple interface with buttons to open each chart type (System, Network, Device)
in its own separate window.

This script is intended to be run as a standalone application, typically called by the main
WLEDVideoSync application.
"""
import argparse
from nicegui import ui, app, native
from src.gui.syscharts import SysCharts, NetCharts, DevCharts

DEV_LIST = []
INTER_PROC_FILE = ''
DARK_MODE = False
NATIVE_UI = False

try:
    from src.gui.niceutils import apply_custom
    from configmanager import NATIVE_UI
except Exception as e:
    print(f'NOT WLEDVideoSync: {e}')
    async def apply_custom():
        pass


@ui.page('/')
async def main_page():
    """The main launcher page with buttons for each chart type."""

    await apply_custom()

    ui.label('WLEDVideoSync Charts').classes('text-2xl font-bold self-center mb-4')

    with ui.card().classes('mx-auto'):
        ui.label('Select a chart to open in a new window.').classes('self-center')
        with ui.row().classes('w-full justify-center gap-4 mt-4'):
            ui.button('System Stats', on_click=lambda: ui.navigate.to('/sysstat', new_tab=True))
            ui.button('Network Stats', on_click=lambda: ui.navigate.to('/netstat', new_tab=True))
            ui.button('Devices Stats', on_click=lambda: ui.navigate.to('/devstat', new_tab=True))

        ui.button('Close', on_click=app.shutdown).classes('mt-6 self-center')


@ui.page('/sysstat', title='System Stats')
async def sys_stat_page():
    await apply_custom()
    sysstat = SysCharts(dark=DARK_MODE)
    await sysstat.setup_ui()


@ui.page('/netstat', title='Network Stats')
async def net_stat_page():
    await apply_custom()
    netstat = NetCharts(dark=DARK_MODE)


@ui.page('/devstat', title='Device Stats')
async def dev_stat_page():
    await apply_custom()
    devstat = DevCharts(dark=DARK_MODE, inter_proc_file=INTER_PROC_FILE)
    await devstat.setup_ui(DEV_LIST)


def main(i_dev_list: list = None, i_inter_proc_file: str = '', i_dark: bool = False):
    """Launches the WLEDVideoSync chart UI as a standalone application.

    This function parses command-line arguments, sets up device and inter-process file
    configuration, and starts the NiceGUI server for chart selection and display.

    Args:
        i_dev_list (list, optional): List of device IPs for the device chart. Defaults to None.
        i_inter_proc_file (str, optional): Path to the inter-process file (shelve). Defaults to None.
        i_dark (bool, optional): Enable dark mode for the chart. Defaults to False.

    ************* Args are used when executed via WLEDVideoSync *****************

    """
    global DEV_LIST, INTER_PROC_FILE, DARK_MODE

    DEV_LIST = i_dev_list
    INTER_PROC_FILE = i_inter_proc_file
    DARK_MODE = i_dark

    parser = argparse.ArgumentParser(description="WLEDVideoSync Chart Launcher")
    parser.add_argument('--run-sys-charts', action='store_true', help='If run from WLEDVideoSync directly.')
    parser.add_argument('--sysstats', action='store_true', help='Launch System Stats chart directly.')
    parser.add_argument('--netstats', action='store_true', help='Launch Network Stats chart directly.')
    parser.add_argument('--devstats', action='store_true', help='Launch Device Stats chart directly.')
    parser.add_argument('--dark', type=bool, help='Enable dark mode for the chart.')
    parser.add_argument('--dev_list', type=str, help='Comma-separated list of device IPs for the device chart.')
    parser.add_argument('--file', type=str, help='Absolute path of the inter process file (shelve).')

    args = parser.parse_args()

    if args.dev_list:
        # Filter out empty strings that can result from an empty --dev_list="" argument
        DEV_LIST = [ip for ip in args.dev_list.split(',') if ip]
    if args.file:
        INTER_PROC_FILE = args.file

    # If the list is still empty, default to localhost
    if not DEV_LIST:
        DEV_LIST = ['127.0.0.1']

    # find an open port for the charts server
    srv_port = native.find_open_port()

    # infinite loop
    ui.run(title='Charts Launcher',
           reload=False,
           port=srv_port,
           native=NATIVE_UI,
           dark=DARK_MODE)


if __name__ == "__main__":
    main()
