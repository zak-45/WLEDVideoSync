"""
a: zak-45
d: 01/04/2025
v: 1.0.0
"""


import asyncio

from str2bool import str2bool
from nicegui import ui, run, app
from src.gui.pyeditor import PythonEditor
import psutil

from configmanager import ConfigManager
from src.gui.niceutils import apply_custom

cfg_mgr = ConfigManager()
py_editor = PythonEditor(cfg_mgr.app_root_path('xtra/scheduler'), use_capture=False, go_back=True)

class Scheduler:
    def __init__(self, Desktop, Media, CastAPI, t_data_buffer):

        self.Desktop = Desktop
        self.Media = Media
        self.CastAPI = CastAPI
        self.Queue = t_data_buffer


    async def find_python_processes(self):
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if process.info['name'] == 'python.exe' or (
                        process.info['cmdline'] and 'python' in process.info['cmdline'][0]
                ):
                    print(f"PID: {process.info['pid']}, Command: {' '.join(process.info['cmdline'] or [])}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass


    async def setup_ui(self):

        dark = ui.dark_mode(self.CastAPI.dark_mode).bind_value_to(self.CastAPI, 'dark_mode')

        apply_custom()

        if str2bool(cfg_mgr.custom_config['animate_ui']):
            # Add Animate.css to the HTML head
            ui.add_head_html("""
            <link rel="stylesheet" href="assets/css/animate.min.css"/>
            """)

        """
        Scheduler page creation
        """
        ui.label('WLEDVideoSync Scheduler').classes('self-center mb-4 text-red-900 text-2xl font-extrabold  dark:text-white md:text-4xl lg:text-5xl')
        with ui.card().tight().classes('self-center w-full'):
            ui.label('scheduler')
            await py_editor.setup_ui()

if __name__ == "__main__":
    from mainapp import Desktop as Dk, Media as Md, CastAPI as Api, t_data_buffer as queue

    py_editor = PythonEditor(cfg_mgr.app_root_path('xtra/scheduler'), use_capture=False, go_back=False)

    app.add_static_files('/assets',cfg_mgr.app_root_path('assets'))
    schedule_app = Scheduler(Dk, Md, Api, queue)

    print('start main')
    @ui.page('/')
    async def main_page():
        print('main page')
        await schedule_app.setup_ui()

    ui.run(reload=False)

    print('End main')
