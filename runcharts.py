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
import asyncio
from nicegui import ui, app, native
from src.gui.syscharts import SysCharts, NetCharts, DevCharts

DEV_LIST = []
INTER_PROC_FILE = ''
DARK_MODE = False
NATIVE_UI = False
parsed_args = None # Global to store parsed command-line arguments

try:
    from src.gui.niceutils import apply_custom
    from configmanager import NATIVE_UI
except Exception as e:
    print(f'NOT WLEDVideoSync: {e}')
    async def apply_custom():
        pass


async def shutdown():
     """Gracefully shut down the application by cleaning up resources first."""
     # This delay gives the client-side a moment to process the shutdown command
     # before the server starts tearing down connections, preventing a race condition.
     await asyncio.sleep(0.1)
     app.shutdown()


@ui.page('/')
async def main_page():
    """The main launcher page with buttons for each chart type."""
    # If a specific chart was requested via command line, redirect immediately.
    if parsed_args:
        if parsed_args.sysstats:
            ui.navigate.to('/sysstat')
            return
        if parsed_args.netstats:
            ui.navigate.to('/netstat')
            return
        if parsed_args.devstats:
            ui.navigate.to('/devstat')
            return

    await apply_custom()

    ui.label('WLEDVideoSync Charts').classes('text-2xl font-bold self-center mb-4')

    with ui.card().classes('mx-auto'):
        ui.label('Select a chart to open in a new window.').classes('self-center')
        with ui.row().classes('w-full justify-center gap-4 mt-4'):
            system = ui.button('System Stats', on_click=lambda: ui.navigate.to('/sysstat', new_tab=True))
            system.tooltip('Show system stats ')
            network = ui.button('Network Stats', on_click=lambda: ui.navigate.to('/netstat', new_tab=True))
            network.tooltip('Show network stats')
            devices = ui.button('Devices Stats', on_click=lambda: ui.navigate.to('/devstat', new_tab=True))
            devices.tooltip('Show device stats')

        close = ui.button('Stop',icon='power_settings_new', on_click=shutdown).classes('mt-6 self-center')
        close.tooltip('Shutdown Chart Launcher application')


@ui.page('/sysstat', title='System Stats')
async def sys_stat_page():
    await apply_custom()
    sysstat = SysCharts(dark=DARK_MODE, direct_launch=parsed_args.sysstats if parsed_args is not None else False)
    await sysstat.setup_ui()


@ui.page('/netstat', title='Network Stats')
async def net_stat_page():
    await apply_custom()
    netstat = NetCharts(dark=DARK_MODE, direct_launch=parsed_args.netstats if parsed_args is not None else False)


@ui.page('/devstat', title='Device Stats')
async def dev_stat_page():
    await apply_custom()
    devstat = DevCharts(dark=DARK_MODE, inter_proc_file=INTER_PROC_FILE, direct_launch=parsed_args.devstats if parsed_args is not None else False)
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
    global DEV_LIST, INTER_PROC_FILE, DARK_MODE, parsed_args

    DEV_LIST = i_dev_list
    INTER_PROC_FILE = i_inter_proc_file
    DARK_MODE = i_dark

    # Disable default help to create a custom one with an alias
    parser = argparse.ArgumentParser(description="WLEDVideoSync Chart Launcher", add_help=False)
    parser.add_argument('-h', '--help', '--more', action='help', help='Show this help message and exit.')
    parser.add_argument('--run-sys-charts', action='store_true', help='Charts Launcher directly (used by WLEDVideoSync).')
    parser.add_argument('--sysstats', action='store_true', help='Launch System Stats chart directly.')
    parser.add_argument('--netstats', action='store_true', help='Launch Network Stats chart directly.')
    parser.add_argument('--devstats', action='store_true', help='Launch Device Stats chart directly.')
    parser.add_argument('--dark', type=bool, help='Enable dark mode for the chart.')
    parser.add_argument('--dev_list', type=str, help='Comma-separated list of device IPs for the device chart.')
    parser.add_argument('--file', type=str, help='Absolute path of the inter process file (shelve).')

    args = parser.parse_args()
    parsed_args = args # Store args globally for the main page to access

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

    # start server & infinite loop
    ui.run(title='Charts Launcher',
           reload=False,
           port=srv_port,
           native=NATIVE_UI,
           dark=DARK_MODE)

    print('End of sys charts')

if __name__ == "__main__":
    main()
