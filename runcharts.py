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

from nicegui import ui, app, native
from mainapp import CastAPI
from src.gui.niceutils import apply_custom
from src.gui.syscharts import SysCharts, NetCharts, DevCharts
from configmanager import NATIVE_UI

@ui.page('/')
async def main_page():
    """The main launcher page with buttons for each chart type."""
    ui.label('WLEDVideoSync Charts').classes('text-2xl font-bold self-center mb-4')

    with ui.card().classes('mx-auto'):
        ui.label('Select a chart to open in a new window.').classes('self-center')
        with ui.row().classes('w-full justify-center gap-4 mt-4'):
            ui.button('System Stats', on_click=lambda: ui.navigate.to('/sysstat', new_tab=True))
            ui.button('Network Stats', on_click=lambda: ui.navigate.to('/netstat', new_tab=True))
            ui.button('Devices Stats', on_click=lambda: ui.navigate.to('/devstat', new_tab=True))

        ui.button('Close', on_click=app.shutdown).classes('mt-6 self-center')

@ui.page('/sysstat')
async def sys_stat_page():
    await apply_custom()
    sysstat = SysCharts(dark=CastAPI.dark_mode)
    await sysstat.setup_ui()

@ui.page('/netstat')
async def net_stat_page():
    await apply_custom()
    netstat = NetCharts(dark=CastAPI.dark_mode)

@ui.page('/devstat')
async def dev_stat_page():
    await apply_custom()
    devstat = DevCharts(dark=CastAPI.dark_mode)

def main(dev_list: list = None, inter_proc_file: str = None):

    srv_port = native.find_open_port()

    ui.run(title='Charts Launcher',
           reload=False,
           port=srv_port,
           native=NATIVE_UI)

if __name__ in {"__main__", "__mp_main__"}:
    main()