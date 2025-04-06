"""
a: zak-45
d: 01/04/2025
v: 1.0.0


"""
from nicegui import ui, run, app
from str2bool import str2bool

from configmanager import ConfigManager
from src.gui.niceutils import apply_custom

cfg_mgr = ConfigManager(logger_name='WLEDLogger')

class SchedulerGUI:
    def __init__(self, Desktop, Media, CastAPI, t_data_buffer):
        self.Desktop = Desktop
        self.Media = Media
        self.CastAPI = CastAPI
        self.queue = t_data_buffer


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
        with ui.card().classes('self-center w-full'):
            with ui.row().classes('self-center w-full'):
                ui.label('schedule')
                ui.label('every')
                ui.number(min=0,max=999,value=0)
                ui.select(['','second','minute','hour','day','week'],label="period").classes('w-20')
                ui.select(['','seconds','minutes','hours','days','weeks'], label="periods").classes('w-20')
                ui.select(['','monday','tuesday','wednesday','thursday','friday','saturday','sunday'], label="day").classes('w-20')
                ui.select(['','at','until']).classes('w-10')
                with ui.input('Time') as time:
                    with ui.menu().props('no-parent-event') as menu:
                        with ui.time().bind_value(time):
                            with ui.row().classes('justify-end'):
                                ui.button('Close', on_click=menu.close).props('flat')
                    with time.add_slot('append'):
                        ui.icon('access_time').on('click', menu.open).classes('cursor-pointer')
                ui.label('do')
                ui.select(['job1','job2','job3'], label='job').classes('w-40')
                ui.space()
                ui.button(icon='add')

        with ui.card().classes('self-center w-full'):
            with ui.row().classes('self-center w-full'):
                ui.label('schedule')
                ui.label('at')
                with ui.input('Date') as date:
                    with ui.menu().props('no-parent-event') as menu:
                        with ui.date().bind_value(date):
                            with ui.row().classes('justify-end'):
                                ui.button('Close', on_click=menu.close).props('flat')
                    with date.add_slot('append'):
                        ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
                with ui.input('Time') as time:
                    with ui.menu().props('no-parent-event') as menu:
                        with ui.time().bind_value(time):
                            with ui.row().classes('justify-end'):
                                ui.button('Close', on_click=menu.close).props('flat')
                    with time.add_slot('append'):
                        ui.icon('access_time').on('click', menu.open).classes('cursor-pointer')
                ui.label('do')
                ui.select(['job1','job2','job3'], label='job').classes('w-40')
                ui.space()
                ui.button(icon='add')

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full'):
                with ui.expansion(text='Job(s)').classes('w-2/3'):
                    ui.label('jobs list')
                ui.space()
                ui.button('cancel all', icon='cancel')

if __name__ == "__main__":
    from mainapp import Desktop as Dk, Media as Md, CastAPI as Api, t_data_buffer as queue

    app.add_static_files('/assets',cfg_mgr.app_root_path('assets'))
    schedule_app = SchedulerGUI(Dk, Md, Api, queue)

    print('start main')
    @ui.page('/')
    async def main_page():
        print('main page')
        await schedule_app.setup_ui()

    ui.run(reload=False)

    print('End main')
