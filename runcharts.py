"""
a: zak-45
d: 10/03/2025
v: 1.1.0

Overview:
This file, `runcharts.py`, defines a standalone launcher application for the various system and device monitoring
dashboards used by WLEDVideoSync. It is designed to be executed as a separate process, typically spawned by the main
application, to ensure that the resource-intensive charting operations do not impact the performance of the core
video streaming logic.

The script creates a simple web-based launcher UI using NiceGUI, which provides buttons to open each specific chart
(System, Network, Device) in a new window or tab. It also handles command-line argument parsing to receive necessary
configuration from the parent process, such as the list of devices to monitor and the UI theme.

Key Architectural Components:

1.  **Command-Line Argument Parsing (`argparse`)**:
    -   The `main()` function uses Python's `argparse` module to accept a variety of command-line flags.
    -   This allows the main WLEDVideoSync application to pass crucial data, such as the list of device IPs
        (`--dev_list`), the path to the inter-process communication file (`--file`), and the dark mode setting (`--dark`).
    -   It also supports direct-launch flags (`--sysstats`, `--netstats`, `--devstats`), which bypass the launcher menu
        and immediately open a specific chart. This is useful for creating direct shortcuts or for testing.

2.  **NiceGUI Page Routing (`@ui.page`)**:
    -   The application defines multiple pages:
        -   A root page (`/`) that serves as the main launcher menu.
        -   Separate pages for each chart type (`/sysstat`, `/netstat`, `/devstat`), each with a unique title.
    -   This multi-page structure allows each chart to run in its own isolated browser tab or native window,
        preventing them from interfering with each other.

3.  **Chart Class Integration**:
    -   The script imports the chart-generating classes (`SysCharts`, `NetCharts`, `DevCharts`) from `syscharts.py`.
    -   On each respective page, it instantiates the appropriate class, passing the configuration (like `dark` mode
        or `inter_proc_file`) that was received via the command-line arguments.

Design Philosophy:
-   **Process Decoupling**: By running as a separate application, the monitoring dashboards are completely decoupled
    from the main WLEDVideoSync process, ensuring stability and performance for the core streaming functionality.
-   **Configurability**: The use of command-line arguments provides a flexible and robust way to configure the charts
    at launch time.
-   **Simplicity**: The launcher UI is intentionally minimal, providing a straightforward way for the user to access
    the detailed monitoring tools.
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
            ui.navigate.to('/sysstats')
            return
        if parsed_args.netstats:
            ui.navigate.to('/netstats')
            return
        if parsed_args.devstats:
            ui.navigate.to('/devstats')
            return

    await apply_custom()

    ui.label('WLEDVideoSync Charts').classes('text-2xl font-bold self-center mb-4')

    with ui.card().classes('mx-auto'):
        ui.label('Select a chart to open in a new window.').classes('self-center')
        with ui.row().classes('w-full justify-center gap-4 mt-4'):
            system = ui.button('System Stats', on_click=lambda: ui.navigate.to('/sysstats', new_tab=True))
            system.tooltip('Show system stats ')
            network = ui.button('Network Stats', on_click=lambda: ui.navigate.to('/netstats', new_tab=True))
            network.tooltip('Show network stats')
            devices = ui.button('Devices Stats', on_click=lambda: ui.navigate.to('/devstats', new_tab=True))
            devices.tooltip('Show device stats')

        close = ui.button('Stop',icon='power_settings_new', on_click=shutdown).classes('mt-6 self-center')
        close.tooltip('Shutdown Chart Launcher application')


@ui.page('/sysstats', title='System Stats')
async def sys_stat_page():
    await apply_custom()
    sysstat = SysCharts(dark=DARK_MODE, direct_launch=parsed_args.sysstats if parsed_args is not None else False)
    await sysstat.setup_ui()


@ui.page('/netstats', title='Network Stats')
async def net_stat_page():
    await apply_custom()
    netstat = NetCharts(dark=DARK_MODE, direct_launch=parsed_args.netstats if parsed_args is not None else False)


@ui.page('/devstats', title='Device Stats')
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
    global DEV_LIST, INTER_PROC_FILE, DARK_MODE, NATIVE_UI, parsed_args

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
    parser.add_argument('--dev_list', type=str, help='Comma-separated list of device IPs for the device chart.')
    parser.add_argument('--dark', action='store_true', help='If present, enable dark mode for the chart.')
    parser.add_argument('--native', action='store_true', help='If present, enable native mode (pywebview).')
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

    #
    if args.dark:
        DARK_MODE = args.dark
    #
    if args.native:
        NATIVE_UI = args.native

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
