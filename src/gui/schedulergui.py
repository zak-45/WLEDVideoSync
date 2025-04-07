"""
a: zak-45
d: 01/04/2025
v: 1.0.0

Overview
This Python file defines a GUI for managing a task scheduler within the WLEDVideoSync application.
It allows users to schedule and manage jobs, providing controls to start/stop the scheduler,
define schedules (recurring or at a specific date/time), and view currently scheduled jobs. It integrates with the
nicegui library for the user interface and leverages a custom scheduler implementation.

Key Components
    SchedulerGUI Class: This class is the core of the file, responsible for creating and managing the scheduler GUI.
    It interacts with other components like Desktop, Media, CastAPI, and a data buffer (t_data_buffer).
    It also optionally integrates with a ConsoleCapture for displaying console output.

    scheduler Instance: An instance of the Scheduler class, initialized with a worker pool and queue,
    handles the actual scheduling and execution of jobs.

    cfg_mgr Instance: An instance of ConfigManager is used for accessing configuration settings,
    such as UI animation preferences and file paths. It also provides a logger.

    jobs Instance: An instance of AllJobs, loaded from a configuration file (jobstosched.py),
    provides the available jobs that can be scheduled.

    setup_ui() Method: This method builds the user interface using nicegui elements. It includes controls for:

        Activating/deactivating the scheduler.
        Defining recurring schedules (interval, time, day of the week).
        Defining one-time schedules (specific date and time).
        Selecting the job to execute.
        Displaying currently scheduled jobs.
        Cancelling all scheduled jobs.
        Optionally displaying a console for debugging.

    Event Handlers: Various event handlers are defined to manage user interactions, such as toggling the scheduler,
    updating the list of scheduled jobs, and adding new jobs to the schedule. For example, the activate_scheduler
    function starts or stops the scheduler based on a switch.

Integration with nicegui: The code heavily utilizes nicegui elements
    (e.g., ui.label, ui.switch, ui.card, ui.expansion) to create the user interface.
    It also uses nicegui's event handling mechanisms.

External Dependencies: The code depends on several external libraries and modules, including nicegui,
    str2bool, custom modules like ConsoleCapture, apply_custom, Scheduler, and managejobs.

"""
from nicegui import ui,app
from str2bool import str2bool

from src.utl.console import ConsoleCapture
from src.gui.niceutils import apply_custom
from src.utl.scheduler import Scheduler
from src.utl.managejobs import *

scheduler = Scheduler(num_workers=2, queue_size=9)
cfg_mgr = ConfigManager()
AllJobs = load_jobs(cfg_mgr.app_root_path('xtra/jobs/jobstosched.py'))
jobs=AllJobs()

class SchedulerGUI:
    """Creates and manages the scheduler GUI.

    Provides a user interface for scheduling and managing jobs, integrating with various
    components of the WLEDVideoSync application.
    """
    def __init__(self, Desktop=None, Media=None, CastAPI=None, t_data_buffer=None, use_capture:bool = False):
        self.use_capture = use_capture
        if self.use_capture:
            self.capture = ConsoleCapture(show_console=False)
        self.log_queue = None
        self.Desktop = Desktop
        self.Media = Media
        self.CastAPI = CastAPI
        self.queue = t_data_buffer

    async def show_running(self):
        print('show running')


    async def setup_ui(self):
        """Sets up the user interface for the scheduler.

        Creates and arranges UI elements for scheduling jobs, including controls for
        activation, recurring/one-time schedules, job selection, and display of
        scheduled jobs.
        """

        def update_sched():
            """Updates the displayed list of scheduled jobs.

            Retrieves the list of scheduled jobs from the scheduler if it's running
            and updates the UI element displaying the list. Logs a warning if the
            scheduler is not running.
            """
            if scheduler.is_running:
                cfg_mgr.logger.info('get all scheduled jobs')
                schedule_list.set_value(scheduler.scheduler.get_jobs())
            else:
                cfg_mgr.logger.warning('scheduler is not running ...')

        def activate_scheduler():
            """Activates or deactivates the scheduler based on the scheduler switch.

            Starts the scheduler if the switch is on, stops it if the switch is off,
            and updates the scheduler status indicator accordingly.
            """
            if scheduler_switch.value:
                cfg_mgr.logger.info('start scheduler')
                scheduler.start()
                scheduler_status.props('color=green')
            else:
                cfg_mgr.logger.info('stop scheduler')
                scheduler.stop()
                scheduler_status.props('color=yellow')

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
        with ui.row(wrap=False).classes('w-1/3 self-center'):
            with ui.card().tight().classes('w-full self-center').props('flat'):
                with ui.row().classes('self-center'):
                    scheduler_switch = ui.switch('activate', value=scheduler.is_running,on_change=activate_scheduler)
                    scheduler_status = ui.icon('history', size='lg', color='yellow').on('click',lambda: self.show_running).style('cursor:pointer')
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
                ui.select(jobs.list, label='job').classes('w-40')
                ui.space()
                ui.button(icon='add_to_queue')

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
                ui.select(jobs.list, label='job').classes('w-40')
                ui.space()
                ui.button(icon='add_to_queue')

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full'):
                with ui.expansion(text='Scheduled Job(s)', icon='task', on_value_change=lambda: update_sched()).classes('w-2/3'):
                    schedule_list = ui.textarea('test')
                ui.space()
                ui.button('cancel all', icon='cancel')

        ui.separator()

        if self.use_capture:
            media_exp_param = ui.expansion('Console', icon='feed', value=False)
            with media_exp_param.classes('w-full bg-sky-800 mt-2'):
                self.capture.setup_ui()


if __name__ == "__main__":
    from mainapp import Desktop as Dk, Media as Md, CastAPI as Api, t_data_buffer as queue

    app.add_static_files('/assets',cfg_mgr.app_root_path('assets'))
    schedule_app = SchedulerGUI(Dk, Md, Api, queue, use_capture=True)

    print('start main')
    @ui.page('/')
    async def main_page():
        print('main scheduler page')
        await schedule_app.setup_ui()

    ui.run(reload=False)

    print('End main')
