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
from nicegui import ui, app
from str2bool import str2bool
from datetime import datetime
from src.utl.console import ConsoleCapture
from src.gui.niceutils import apply_custom
from src.utl.scheduler import Scheduler
from src.gui.pyeditor import PythonEditor
from src.utl.managejobs import *

cfg_mgr = ConfigManager(logger_name='WLEDLogger')
scheduler = Scheduler(num_workers=2, queue_size=9)

schedule_editor = PythonEditor(file_to_load=cfg_mgr.app_root_path('xtra/scheduler/WLEDScheduler.py'),
                               coldtype=False,
                               use_capture=False,
                               go_back=False)

job_editor = PythonEditor(file_to_load=cfg_mgr.app_root_path('xtra/jobs/jobstosched.py'),
                               coldtype=False,
                               use_capture=False,
                               go_back=False)


AllJobs = load_jobs(cfg_mgr.app_root_path('xtra/jobs/jobstosched.py'))

WLEDScheduler = scheduler.scheduler
jobs = AllJobs()

def format_job_descriptions(job_list, history=False, filter_tag=None):
    """Formats job descriptions for display.

    If `filter_tag` is set, only include jobs with that tag.
    """
    if not job_list:
        return "No jobs scheduled."

    lines = []
    
    for job in job_list:
        if filter_tag and filter_tag not in job.tags:
            continue

        tag_info = '[ONCE]' if any('one-time' in t for t in job.tags) else '[RECURRING]'

        # Try to extract job metadata
        try:
            job_name = job.job_func._job_name
        except AttributeError:
            job_name = job.job_func.__name__

        try:
            run_time = job.job_func._run_time.strftime('%Y-%m-%d %H:%M')
            time_info = f"(scheduled for {run_time})"
        except AttributeError:
            time_info = ""

        job_str = repr(job) if history else f"{tag_info} {job_name} {time_info} => {job}"
        lines.append(job_str)

    return "\n".join(lines) if lines else "No matching jobs."

class SchedulerGUI:
    """Creates and manages the scheduler GUI.

    Provides a user interface for scheduling and managing jobs, integrating with various
    components of the WLEDVideoSync application.
    """

    def __init__(self, Desktop=None, Media=None, CastAPI=None, t_data_buffer=None, use_capture: bool = False):
        self.use_capture = use_capture
        self.log_queue = None
        self.Desktop = Desktop
        self.Media = Media
        self.CastAPI = CastAPI
        self.queue = t_data_buffer
        if self.use_capture:
            self.capture = ConsoleCapture(show_console=False)

    @staticmethod
    async def show_running():
        """Displays currently running scheduled jobs.

        Opens a dialog box showing the current scheduled jobs retrieved from the scheduler.
        """
        with ui.dialog().props('full-width') as running_jobs:
            running_jobs.open()
            with ui.card().classes('w-full'):
                with ui.textarea() as schedule_list:
                    schedule_list.classes('w-full')
                    schedule_list.set_value(format_job_descriptions(scheduler.scheduler.get_jobs(), history=True))
                ui.button('close', on_click=running_jobs.close)

    async def setup_ui(self):
        """Sets up the user interface for the scheduler.

        Creates and arranges UI elements for scheduling jobs, including controls for
        activation, recurring/one-time schedules, job selection, and display of
        scheduled jobs.
        """

        def cancel_all_jobs():
            """Clears all jobs from the scheduler."""
            try:
                slide_item.reset()
                scheduler.scheduler.clear()
                update_sched()  # Update the list after clearing
                ui.notify('All scheduled jobs cancelled.', type='positive')
                cfg_mgr.logger.info('All scheduled jobs cancelled.')
            except Exception as e:
                ui.notify(f'Error cancelling jobs: {e}', type='negative')
                cfg_mgr.logger.error(f'Error cancelling jobs: {e}')

        def update_sched():
            """Updates the displayed list of scheduled jobs.

            Retrieves the list of scheduled jobs from the scheduler if it's running
            and updates the UI element displaying the list. Logs a warning if the
            scheduler is not running.
            """
            if scheduler.is_running:
                schedule_list.set_value(format_job_descriptions(scheduler.scheduler.get_jobs()))

        def activate_scheduler():
            """Activates or deactivates the scheduler based on the scheduler switch.

            Starts the scheduler if the switch is on, stops it if the switch is off,
            and updates the scheduler status indicator accordingly.
            """
            if scheduler_switch.value:
                cfg_mgr.logger.info('start scheduler')
                scheduler.start()
                scheduler_status.props('color=green')
                clock_card.set_visibility(True)
                analog_clock_card.set_visibility(False)
            else:
                cfg_mgr.logger.info('stop scheduler')
                scheduler.stop()
                scheduler_status.props('color=yellow')
                clock_card.set_visibility(False)
                analog_clock_card.set_visibility(True)

        def add_recurring_job():
            """Adds a recurring job to the scheduler."""
            try:
                interval = int(interval_input.value)
                period = period_select.value
                day = day_select.value
                time_str = time_recurring.value
                job_name = job_select_recurring.value

                if not job_name:
                    ui.notify('Please select a job.', type='warning')
                    return

                if not period:
                    ui.notify('Please select a period.', type='warning')
                    return

                if interval == 0:
                    ui.notify('Please set an interval.', type='warning')
                    return

                if period != 'second' and not time_str:
                    ui.notify('Please set a time.', type='warning')
                    return

                if period == 'week' and not day:
                    ui.notify('Please select a day of the week.', type='warning')
                    return

                job_func = jobs.get_job(job_name)
                if job_func is None:
                    ui.notify(f'Error scheduling job: {job_name}', type='negative')
                    return

                sched = WLEDScheduler.every(interval)

                if period == 'second':
                    sched = sched.seconds
                elif period == 'minute':
                    sched = sched.minutes
                elif period == 'hour':
                    sched = sched.hours
                elif period == 'day':
                    sched = sched.days
                    sched = sched.at(time_str)
                elif period == 'week':
                    sched = getattr(sched, day).at(time_str)

                sched.do(scheduler.send_job_to_queue, job_func).tag('WLEDVideoSync', job_name)

                update_sched()
                ui.notify(f'Job \"{job_name}\" scheduled successfully.', type='positive')

            except Exception as e:
                ui.notify(f'Error scheduling job: {e}', type='negative')

        def schedule_one_time_job(run_at: datetime, job_func, job_name: str = ""):
            """Schedules a one-time job using the schedule module."""

            def one_time_wrapper():
                now = datetime.now()
                if now >= run_at:
                    scheduler.send_job_to_queue(job_func)
                    WLEDScheduler.clear(tag=f'one-time-{job_name}')

            one_time_wrapper._job_name = job_name
            one_time_wrapper._run_time = run_at  # 💡 store the scheduled datetime

            WLEDScheduler.every(1).minutes.do(one_time_wrapper).tag('WLEDVideoSync', 'one-time', f'one-time-{job_name}')

        def add_one_time_job():
            """Adds a one-time job using schedule-based wrapper."""
            try:
                job_name = job_select_one_time.value
                date_str = date_one_time.value
                time_str = time_one_time.value

                if not job_name:
                    ui.notify('Please select a job.', type='warning')
                    return

                if not date_str or not time_str:
                    ui.notify('Please select a valid date and time.', type='warning')
                    return

                job_func = jobs.get_job(job_name)
                if job_func is None:
                    ui.notify(f'Job not found: {job_name}', type='negative')
                    return

                run_at_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                schedule_one_time_job(run_at_time, job_func, job_name)

                update_sched()
                ui.notify(f'Job \"{job_name}\" scheduled for {run_at_time}.', type='positive')

            except Exception as e:
                ui.notify(f'Error scheduling job: {e}', type='negative')

        async def scheduler_timer_action():
            """Updates the scheduler status indicator color.

            Sets the color of the scheduler status icon to green if the scheduler
            is active, and yellow otherwise.
            """
            if scheduler_switch.value is True:
                scheduler_status.props('color=green')
                update_sched()
            else:
                scheduler_status.props('color=yellow')

        dark = ui.dark_mode(self.CastAPI.dark_mode).bind_value_to(self.CastAPI, 'dark_mode')

        apply_custom()

        if str2bool(cfg_mgr.custom_config['animate_ui']):
            # Add Animate.css to the HTML head
            ui.add_head_html("""
            <link rel="stylesheet" href="assets/css/animate.min.css"/>
            <link rel="stylesheet" href="assets/css/clock.css"/>
            <link rel="stylesheet" href="assets/css/analog-clock.css"/>
            """)

        ui.add_body_html("""
              <script src="assets/js/clock.js"></script>
              <script src="assets/js/analog-clock.js"></script>
        """
        )

        """
        scheduler timer 
        """
        scheduler_timer = ui.timer(int(cfg_mgr.app_config['timer']), callback=scheduler_timer_action)

        """
        Scheduler page creation
        """
        ui.label('WLEDVideoSync Scheduler').classes(
            'self-center mb-4 text-red-900 text-2xl font-extrabold  dark:text-white md:text-4xl lg:text-5xl')
        with ui.row(wrap=False).classes('w-1/3 self-center'):
            with ui.card().tight().classes('w-full self-center').props('flat'):
                with ui.row().classes('self-center'):
                    scheduler_switch = ui.switch('activate', value=scheduler.is_running,
                                                 on_change=activate_scheduler)
                    scheduler_status = ui.icon('history', size='lg', color='yellow').on('click',
                                                                                        lambda: self.show_running()).style(
                        'cursor:pointer')
        """
         add clock
        """
        with ui.card().tight().classes('self-center') as clock_card:
            clock_card.set_visibility(False)
            ui.html("""
                 <div class="wled-clock">
                     <div class="container">
                         <div class="clock">
                             <span id="date">YYYY-MM-DD</span>
                             <span>-</span>
                             <span id="hour">HH</span>
                             <span>:</span>
                             <span id="min">MM</span>
                             <span>:</span>
                             <span id="sec">SS</span>
                         </div>
                     </div>
                 </div>
             """)
        #
        """
         add analog clock
        """
        with ui.card().tight().classes('self-center') as analog_clock_card:
            analog_clock_card.set_visibility(True)
            ui.html("""
                <!-- Analog Clock HTML -->
                <div class="analog-clock-container">
                  <div class="clock-face">
                    <div class="hand hour-hand" id="analog-hour"></div>
                    <div class="hand minute-hand" id="analog-min"></div>
                    <div class="hand second-hand" id="analog-sec"></div>
                    <div class="center-dot"></div>
                    <div class="marker marker-12"></div>
                    <div class="marker marker-3"></div>
                    <div class="marker marker-6"></div>
                    <div class="marker marker-9"></div>
                  </div>
                </div>
             """)
        #
        with ui.card().classes('self-center w-full'):
            with ui.row().classes('self-center w-full'):
                ui.label('schedule')
                ui.label('every')
                interval_input = ui.number(min=0, max=999, value=0)
                period_select = ui.select(['', 'second', 'minute', 'hour', 'day', 'week'], label="period").classes(
                    'w-20')
                # ui.select(['', 'seconds', 'minutes', 'hours', 'days', 'weeks'], label="periods").classes('w-20')
                day_select = ui.select(
                    ['', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
                    label="day").classes('w-20')
                ui.select(['', 'at', 'until']).classes('w-10')
                with ui.input('Time') as time_recurring:
                    with ui.menu().props('no-parent-event') as menu:
                        with ui.time().bind_value(time_recurring):
                            with ui.row().classes('justify-end'):
                                ui.button('Close', on_click=menu.close).props('flat')
                    with time_recurring.add_slot('append'):
                        ui.icon('access_time').on('click', menu.open).classes('cursor-pointer')
                ui.label('do')
                job_select_recurring = ui.select(jobs.names, label='job').classes('w-40')
                ui.space()
                ui.button(icon='add_to_queue', on_click=add_recurring_job)

        with ui.card().classes('self-center w-full'):
            with ui.row().classes('self-center w-full'):
                ui.label('schedule')
                ui.label('at')
                with ui.input('Date') as date_one_time:
                    with ui.menu().props('no-parent-event') as menu:
                        with ui.date().bind_value(date_one_time):
                            with ui.row().classes('justify-end'):
                                ui.button('Close', on_click=menu.close).props('flat')
                    with date_one_time.add_slot('append'):
                        ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
                with ui.input('Time') as time_one_time:
                    with ui.menu().props('no-parent-event') as menu:
                        with ui.time().bind_value(time_one_time):
                            with ui.row().classes('justify-end'):
                                ui.button('Close', on_click=menu.close).props('flat')
                    with time_one_time.add_slot('append'):
                        ui.icon('access_time').on('click', menu.open).classes('cursor-pointer')
                ui.label('do')
                job_select_one_time = ui.select(jobs.names, label='job').classes('w-40')
                ui.space()
                ui.button(icon='add_to_queue', on_click=add_one_time_job)

        with ui.card().tight().classes('w-full').props('flat'):
            with ui.row().classes('w-full'):
                ui.space()
                ui.button('editor', on_click=lambda: editor_row.set_visibility(not editor_row.visible))
                with ui.row().classes('w-full') as editor_row:
                    editor_row.set_visibility(False)
                    with ui.expansion('Custom Schedule', icon='feed', value=False):
                        await schedule_editor.setup_ui()
                    with ui.expansion('Jobs', icon='feed', value=False):
                        await job_editor.setup_ui()

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full'):
                with ui.expansion(text='Scheduled Job(s)', icon='task',
                                  on_value_change=lambda: update_sched()).classes('w-2/3'):
                    schedule_list = ui.textarea().classes('w-full')
                ui.space()
                with ui.slide_item('Cancel All') as slide_item:
                    slide_item.classes('bg-sky-800')
                    with slide_item.right():
                        ui.button(icon='cancel',color='red', on_click=cancel_all_jobs)
                    with slide_item.left():
                        ui.button(icon='cancel',color='red', on_click=cancel_all_jobs)

        ui.separator()

        if self.use_capture:
            sched_exp_param = ui.expansion('Console', icon='feed', value=False)
            with sched_exp_param.classes('w-full bg-sky-800 mt-2'):
                self.capture.setup_ui()


if __name__ == "__main__":
    from mainapp import Desktop as Dk, Media as Md, CastAPI as Api, t_data_buffer as queue

    app.add_static_files('/assets', cfg_mgr.app_root_path('assets'))
    schedule_app = SchedulerGUI(Dk, Md, Api, queue, use_capture=True)

    print('start main')

    @ui.page('/')
    async def main_page():
        print('main scheduler page')
        await schedule_app.setup_ui()

        ui.button('shutdown', on_click=app.shutdown).classes('self-center')

    ui.run(reload=False)

    print('End main')
