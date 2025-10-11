"""
a: zak45
d: 02/04/2024
v: 1.0.0

CastAPI

Cast media to ddp device(s)

DESKTOP: cast your full screen or a window content
    capture frames

MEDIA: cast an image / video / capture device
    capture frames
    cast image with Websocket
    create matrix based on ddp devices... so cast to a BIG one

+
API: FastAPI, for integration with third party application (e.g. Chataigne)

Web GUI based on NiceGUI

# 27/05/2024: cv2.imshow with import av  freeze

"""
import asyncio
import shelve
import sys
import queue
import tkinter as tk

from threading import current_thread
from subprocess import Popen
from datetime import datetime
from PIL import Image

from src.cst import desktop, media
from src.gui import niceutils as nice
from src.net.discover import HTTPDiscovery as Net
from src.gui.niceutils import apply_custom, media_dev_view_page, discovery_net_notify, net_view_button
from src.gui.niceutils import AnimatedElement as Animate, LogElementHandler
from src.gui.castcenter import CastCenter
from src.gui.schedulergui import SchedulerGUI
from src.txt.coldtypemp import RUNColdtype
from src.gui.pyeditor import PythonEditor
from src.gui.videoplayer import VideoPlayer

from src.utl.presets import *
from src.api.api import *

from configmanager import cfg_mgr, PLATFORM, WLED_PID_TMP_FILE, LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.main')
main_logger = logger_manager.logger

Desktop = desktop.CASTDesktop()
Media = media.CASTMedia()
Netdevice = Net()

# to share data between threads and main
t_data_buffer = queue.Queue()  # create a thread safe queue

main_page_url = '/'
cast_center_url = '/Cast-Center'

"""
Define root page based on ini
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ and cfg_mgr.app_config is not None:

    if cfg_mgr.app_config['init_screen'].lower() == 'center':
        main_page_url = '/main'
        cast_center_url = '/'
        root_page = '/Cast-Center'
    else:
        root_page = '/'

"""
Actions to do at application initialization 
"""
async def init_actions():
    """ Done at start of app and before GUI available """

    if '--run-mobile-server' in sys.argv:
        return
    
    CastAPI.loop = asyncio.get_running_loop()

    main_logger.info(f'Main running {current_thread().name}')
    main_logger.info(f'Root page : {root_page}')
    main_logger.info(f"Scheduler enabled : {cfg_mgr.scheduler_config['enable']}")

    # Apply some default params only once
    if str2bool(cfg_mgr.app_config['init_config_done']) is not True:

        def on_ok_click():
            # Close the window when OK button is clicked
            root.destroy()

        # Create the main window
        root = tk.Tk()
        root.title("WLEDVideoSync Information")
        root.geometry("820x460")  # Set the size of the window
        root.configure(bg='#657B83')  # Set the background color

        Utils.update_ini_key('config/WLEDVideoSync.ini', 'app', 'init_config_done', 'True')

        # Define the window's contents
        info_text = "Some Params has changed.... restart your app"
        info_label = tk.Label(root, text=info_text, bg='#657B83', fg='white', justify=tk.LEFT)
        info_label.pack(padx=10, pady=10)

        # Create the OK button
        ok_button = tk.Button(root, text="Ok", command=on_ok_click, bg='gray', fg='white')
        ok_button.pack(pady=10)

        # Start the Tkinter event loop
        root.mainloop()

        sys.exit()

    try:
        # Set Fonts path for app
        if cfg_mgr.app_config['font_file'] != '':
            font_dir = os.path.dirname(cfg_mgr.app_config['font_file'])
            font_url = "/FontsPath"
            app.add_static_files(font_url, font_dir)

        # Apply presets
        if str2bool(cfg_mgr.preset_config['load_at_start']):
            if cfg_mgr.preset_config['filter_media'] != '':
                main_logger.debug(f"apply : {cfg_mgr.preset_config['filter_media']} to filter Media")
                await load_filter_preset('Media', Media, interactive=False, file_name=cfg_mgr.preset_config['filter_media'])
            if cfg_mgr.preset_config['filter_desktop'] != '':
                main_logger.debug(f"apply : {cfg_mgr.preset_config['filter_desktop']} to filter Desktop")
                await load_filter_preset('Desktop', Desktop, interactive=False, file_name=cfg_mgr.preset_config['filter_desktop'])
            if cfg_mgr.preset_config['cast_media'] != '':
                main_logger.debug(f"apply : {cfg_mgr.preset_config['cast_media']} to cast Media")
                await load_cast_preset('Media', Media, interactive=False, file_name=cfg_mgr.preset_config['cast_media'])
            if cfg_mgr.preset_config['cast_desktop'] != '':
                main_logger.debug(f"apply : {cfg_mgr.preset_config['cast_desktop']} to cast Desktop")
                await load_cast_preset('Desktop', Desktop, interactive=False, file_name=cfg_mgr.preset_config['cast_desktop'])

        # check if linux and wayland
        if PLATFORM == 'linux' and os.getenv('WAYLAND_DISPLAY') is not None:
            main_logger.error('Wayland detected, preview should not work !!. Switch to X11 session if want to see preview.')

        # start scheduler
        if str2bool(cfg_mgr.scheduler_config['enable']) and str2bool(cfg_mgr.scheduler_config['activate']):
            main_logger.debug('start scheduler')
            await scheduler_app.start_scheduler()
            job_to_start = cfg_mgr.scheduler_config['start_job_name']
            # execute job if set
            if job_to_start != '':
                from src.gui.schedulergui import jobs
                main_logger.debug(f'job to start: {job_to_start}')
                # put the job to queue
                if jobs.get_job(job_to_start):
                    start_time = datetime.now()
                    job_to_run = jobs.get_job(job_to_start)
                    scheduler_app.schedule_one_time_job(start_time, job_to_run)
                else:
                    main_logger.error(f'jobs to start not found : {job_to_start}')

    except Exception as e:
        main_logger.error(f"Error on app startup {e}")

"""
Class
"""
class CastAPI:

    dark_mode = False
    netstat_process = None
    charts_row = None
    player = None
    video_fps = 0
    video_frames = 0
    current_frame = 0
    progress_bar = None
    cpu_chart = None
    video_slider = None
    media_button_sync = None
    slider_button_sync = None
    type_sync = 'none'  # none, slider , player
    last_type_sync = ''  # slider , player
    search_areas = []  # contains YT search
    media_cast = None
    media_cast_run = None
    desktop_cast = None
    desktop_cast_run = None
    total_frames = 0
    total_packets = 0
    ram = 0
    cpu = 0
    w_image = None
    windows_titles = {}
    new_viinput_value = ''
    root_timer = None
    player_timer = None
    info_timer = None
    control_panel = None
    loop = None

    def __init__(self):
        pass

# Instantiate Cast Center with Desktop and Media
cast_app = CastCenter(Desktop, Media, CastAPI, t_data_buffer)
# Instantiate SchedulerGUI with Desktop and Media
scheduler_app = SchedulerGUI(Desktop, Media, CastAPI, t_data_buffer, True)
# Instantiate API to pass Desktop and Media
api_data = ApiData(Desktop, Media, Netdevice, t_data_buffer)
# Instantiate VideoPlayer with Media
video_app = VideoPlayer(Media, CastAPI, t_data_buffer)

"""
NiceGUI
"""


@ui.page(main_page_url)
async def main_page():
    """
    Root page definition
    """
    dark = ui.dark_mode(CastAPI.dark_mode).bind_value_to(CastAPI, 'dark_mode')

    await apply_custom()

    if str2bool(cfg_mgr.custom_config['animate_ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="assets/css/animate.min.css"/>
        """)

    """
    timer created on main page run to refresh datas
    """
    #if CastAPI.root_timer is None:
    CastAPI.root_timer = ui.timer(int(cfg_mgr.app_config['timer']), callback=root_timer_action)

    """
    Header with button menu
    """
    await nice.head_menu(name='Main', target='/', icon='home')

    """
    App info
    """
    if str2bool(cfg_mgr.custom_config['animate_ui']):
        head_row_anim = Animate(ui.row, animation_name_in='backInDown', duration=1)
        head_row = head_row_anim.create_element()
    else:
        head_row = ui.row()

    with head_row.classes('w-full no-wrap'):
        ui.label('DESKTOP: Cast Screen / Window content').classes('bg-slate-400 w-1/3')
        with ui.card().classes('bg-slate-400 w-1/3'):
            img = ui.image("assets/favicon.ico").classes('self-center')
            img.on('click', lambda: animate_toggle(img))
            img.style('cursor: pointer')
            img.tailwind.border_width('4').width('8')
        ui.label('MEDIA: Cast Image / Video / Capture Device (e.g. USB Camera ...)').classes('bg-slate-400 w-1/3')

    """
    WLEDVideoSync image
    """

    ui.separator().classes('mt-6')
    CastAPI.w_image = ui.image("assets/Source-intro.png").classes('self-center')
    CastAPI.w_image.classes(add='animate__animated')
    CastAPI.w_image.tailwind.border_width('8').width('1/6')

    """
    Video player
    """
    if str2bool(cfg_mgr.custom_config['player']):
        await video_app.video_player_page()
        CastAPI.player.set_visibility(False)

    """
    Row for Cast /Filters / info / Run / Close 
    """

    await control_panel_page()

    ui.separator().classes('mt-6')

    """
    Log display
    """

    if str2bool(cfg_mgr.app_config['log_to_main']):
        with ui.expansion('Show log', icon='feed').classes('w-full'):
            log_ui = ui.log(max_lines=250).classes('w-full h-30 bg-black text-white')
            # logging Level
            main_logger.setLevel(cfg_mgr.app_config['log_level'].upper())
            # handler
            log_ui_handler = LogElementHandler(log_ui)
            main_logger.addHandler(log_ui_handler)
            ui.context.client.on_disconnect(lambda: main_logger.removeHandler(log_ui_handler))
            # clear / load log file
            with ui.row().classes('w-full'):
                ui.button('Clear Log', on_click=lambda: log_ui.clear()).tooltip('Erase the log')
                dialog = ui.dialog().classes('w-full') \
                    .props(add='maximized transition-show="slide-up" transition-hide="slide-down"')
                with (dialog, ui.card().classes('w-full console-output')):
                    log_filename = cfg_mgr.app_root_path('log/WLEDVideoSync.log')
                    if os.path.isfile(log_filename):
                        # file exists
                        with open(log_filename) as my_file:
                            log_data = my_file.read()
                    else:
                        log_data = 'ERROR Log File Not Found ERROR'
                        main_logger.warning(f'Log File Not Found {log_filename}')
                    ui.button('Close', on_click=dialog.close, color='red')
                    log_area = ui.textarea(value=log_data).classes('w-full').props(add='bg-color=blue-grey-4')
                    log_area.props(add="rows='25'")
                ui.button('See Log file', on_click=dialog.open).tooltip('Load log data from file.')

    """
    Footer : usefully links help
    """
    with ui.footer(value=False).classes('items-center bg-red-900') as footer:
        ui.switch("Light/Dark Mode", on_change=dark.toggle).classes('bg-red-900').tooltip('Change Layout Mode')

        await net_view_button(show_only=False)

        ui.button('Run discovery', on_click=discovery_net_notify, color='bg-red-800')
        ui.button('SysStats', on_click=charts_select, color='bg-red-800')
        CastAPI.charts_row = ui.row().classes('w-full no-wrap')
        with CastAPI.charts_row:
            with ui.card().classes('w-1/3'):
                ui.button('Device', on_click=dev_stats_info_page)

            with ui.card().classes('w-1/3'):
                ui.button('Network', on_click=net_stats_info_page)

            with ui.card().classes('w-1/3'):
                ui.button('System', on_click=sys_stats_info_page)
        CastAPI.charts_row.set_visibility(False)
        root_page_url = Utils.root_page()
        if root_page_url == '/Cast-Center':
            go_to_url = '/'
        else:
            go_to_url = '/Cast-Center'
        ui.button('Center', on_click=lambda: ui.navigate.to(go_to_url))
        ui.button('Fonts', on_click=font_select, color='bg-red-800')
        ui.button('Config', on_click=lambda: ui.navigate.to('/config_editor'), color='bg-red-800')
        ui.button('PYEditor', on_click=lambda: ui.navigate.to('/Pyeditor'), color='bg-red-800')
        ui.button('shutdown', on_click=app.shutdown)
        with ui.row().classes('absolute inset-y-0 right-0.5 bg-red-900'):
            ui.link('® Zak-45 ' + str(datetime.now().strftime('%Y')), 'https://github.com/zak-45', new_tab=True) \
                .classes('text-white')
            ui.link('On-Line Help', 'https://github.com/zak-45/WLEDVideoSync?tab=readme-ov-file#user-guide', new_tab=True) \
                .tooltip('Go to documentation').classes('text-white')

    with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
        with ui.button(on_click=footer.toggle).props(add='round outline'):
            ui.image('assets/favicon.ico').classes('rounded-full w-8 h-8')


@ui.page('/Manage')
async def main_page_cast_manage():
    """ Cast manage with full details page """

    ui.dark_mode(CastAPI.dark_mode)

    await apply_custom()

    """
    Header with button menu
    """
    await nice.head_menu(name='Manage', target='/Manage', icon='video_settings')

    """
    Main tabs infos
    """
    await tabs_info_page()

    """
    Footer
    """
    with ui.footer():
        await net_view_button(show_only=False)

        await media_dev_view_page()


@ui.page('/Player')
async def run_video_player_page():
    """
    timer created on video creation to refresh datas
    """
    if str2bool(cfg_mgr.custom_config['animate_ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="assets/css/animate.min.css"/>
        """)
    #
    #if CastAPI.player_timer is None:
    CastAPI.player_timer = ui.timer(int(cfg_mgr.app_config['timer']), callback=player_timer_action)
    await video_app.video_player_page()


@ui.page('/Desktop')
async def main_page_desktop():
    """
    Desktop param page
    """
    ui.dark_mode(CastAPI.dark_mode)
    await apply_custom()
    await nice.head_menu(name='Desktop Params', target='/Desktop', icon='computer')

    async def validate():
        # retrieve matrix setup from wled and set w/h
        if Desktop.wled:
            Desktop.scale_width, Desktop.scale_height = await Utils.get_wled_matrix_dimensions(Desktop.host)
        ui.navigate.reload()

    def on_input_new_viinput(x):
        if x.args != '':
            CastAPI.new_viinput_value = x.args

    async def new_viinput_option():
        if CastAPI.new_viinput_value is not None and CastAPI.new_viinput_value not in new_viinput.options:
            new_options = new_viinput.options
            new_options.append(CastAPI.new_viinput_value)
            new_viinput.set_options(new_options)
            new_viinput.value = CastAPI.new_viinput_value
        await update_attribute_by_name('Desktop', 'viinput', str(new_viinput.value))

    if str2bool(cfg_mgr.custom_config['animate_ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="assets/css/animate.min.css"/>
        """)

    columns_a = [
        {'name': 'rate', 'label': 'FPS', 'field': 'rate', 'align': 'left'},
        {'name': 'scale_width', 'label': 'W', 'field': 'scale_width'},
        {'name': 'scale_height', 'label': 'H', 'field': 'scale_height'}
    ]
    rows_a = [
        {'id': 0, 'rate': Desktop.rate, 'scale_width': Desktop.scale_width, 'scale_height': Desktop.scale_height}
    ]
    columns_b = [
        {'name': 'wled', 'label': 'WLED', 'field': 'wled', 'align': 'left'},
        {'name': 'host', 'label': 'IP', 'field': 'host'}
    ]
    rows_b = [
        {'id': 0, 'wled': Desktop.wled, 'host': Desktop.host}
    ]
    columns_c = [
        {'name': 'capture', 'label': 'Capture', 'field': 'capture_methode', 'align': 'left'},
        {'name': 'viinput', 'label': 'Input', 'field': 'viinput', 'align': 'left'},
        {'name': 'viformat', 'label': 'Method', 'field': 'viformat'},
        {'name': 'preview', 'label': 'Preview', 'field': 'preview'}
    ]
    rows_c = [
        {'id': 0, 'capture_methode': Desktop.capture_methode,
         'viinput': Desktop.viinput, 'viformat': Desktop.viformat, 'preview': Desktop.preview}
    ]
    columns_d = [
        {'name': 'vooutput', 'label': 'Output', 'field': 'vooutput', 'align': 'left'},
        {'name': 'voformat', 'label': 'Format', 'field': 'voformat'},
        {'name': 'vo_code', 'label': 'Codec', 'field': 'vo_codec'}
    ]
    rows_d = [
        {'id': 0, 'vooutput': Desktop.vooutput, 'voformat': Desktop.voformat, 'vo_codec': Desktop.vo_codec}
    ]

    columns_e = [
        {'name': 'multicast', 'label': 'MultiCast', 'field': 'multicast', 'align': 'left'},
        {'name': 'matrix-x', 'label': 'H', 'field': 'matrix-x'},
        {'name': 'matrix-y', 'label': 'V', 'field': 'matrix-y'}
    ]
    rows_e = [
        {'id': 0, 'multicast': Desktop.multicast, 'matrix-x': Desktop.cast_x, 'matrix-y': Desktop.cast_y}
    ]

    exp_param = ui.expansion('Parameters', icon='settings', value=True)
    with exp_param.classes('w-full bg-sky-800'):

        with ui.row():
            await nice.cast_icon(Desktop)
            manage_cast_presets('Desktop', Desktop)

        with ui.row():
            ui.table(columns=columns_a, rows=rows_a).classes('w-60')
            ui.table(columns=columns_b, rows=rows_b).classes('w-60')
            ui.table(columns=columns_c, rows=rows_c).classes('w-60')
            ui.table(columns=columns_d, rows=rows_d).classes('w-60')
            ui.table(columns=columns_e, rows=rows_e).classes('w-60')

            with ui.grid(columns=2):
                ui.label('Protocol:')
                ui.label(Desktop.protocol)

                ui.label('Port:')
                ui.label(str(Desktop.port))

                ui.label('No of Packet:')
                ui.label(str(Desktop.retry_number))

    if str2bool(cfg_mgr.custom_config['animate_ui']):
        exp_edit_param_anim = Animate(ui.expansion, animation_name_in='backInDown', duration=1)
        exp_edit_param = exp_edit_param_anim.create_element()
    else:
        exp_edit_param = ui.expansion()

    exp_edit_param.text = 'Edit'
    exp_edit_param.props(add="icon='edit'")
    exp_edit_param.classes('w-full bg-sky-800')
    exp_edit_param.on_value_change(lambda: exp_param.close())

    with exp_edit_param:
        with ui.row():
            ui.icon('restore_page', color='blue', size='md') \
                .style('cursor: pointer').tooltip('Click to Validate/Refresh') \
                .on('click', lambda: validate())

            with ui.card():
                await nice.edit_rate_x_y(Desktop)

            with ui.card():

                await nice.edit_ip(Desktop)

            with ui.card():
                new_capture_methode = ui.select(options=['av','mss'], label='Capture Methode').style(add='width:120px')
                new_capture_methode.bind_value(Desktop,'capture_methode')

            with ui.card():
                input_options=['desktop','area','win=','queue']
                if PLATFORM == 'linux':
                    input_options.insert(0,os.getenv('DISPLAY'))
                elif PLATFORM == 'darwin':
                    input_options.insert(0,'default:none')
                new_viinput = ui.select(options=input_options,label='Input', new_value_mode='add-unique')
                new_viinput.tooltip('Type data to capture, "area" for screen selection, "win=xxxxx" for a screen or queue')
                # Bind the change event to trigger the update
                new_viinput.on('input-value', lambda x: on_input_new_viinput(x))
                new_viinput.on('blur', lambda: new_viinput_option())
                #
                new_preview = ui.checkbox('Preview')
                new_preview.bind_value(Desktop, 'preview')
                new_preview.tooltip('Show preview window')
                new_viformat = ui.input('Format', value=Desktop.viformat)
                new_viformat.bind_value(Desktop, 'viformat')
                new_vi_codec = ui.input('Codec', value=Desktop.vi_codec)
                new_vi_codec.bind_value(Desktop, 'vi_codec')
                with ui.row():
                    ui.number('', value=Desktop.monitor_number, min=-1, max=1).classes('w-10') \
                        .bind_value(Desktop, 'monitor_number', forward=lambda value: int(value or 0)) \
                        .tooltip('Enter monitor number')
                    ui.button('ScreenArea', on_click=lambda: Utils.select_sc_area(Desktop)) \
                        .tooltip('Select area from monitor')

            with ui.card():
                new_vooutput = ui.input('Output', value=str(Desktop.vooutput))
                new_vooutput.bind_value(Desktop, 'vooutput')
                new_vooutput.tooltip('Experimental feature: enter udp:// rtsp:// etc...')
                new_voformat = ui.input('Format', value=Desktop.voformat)
                new_voformat.bind_value(Desktop, 'voformat')
                ui.button('formats', on_click=nice.display_formats)
                new_vo_codec = ui.input('Codec', value=Desktop.vo_codec)
                new_vo_codec.bind_value(Desktop, 'vo_codec')
                ui.button('Codecs', on_click=nice.display_codecs)

            with ui.card():

                await nice.edit_capture(Desktop)

            with ui.card():

                await nice.edit_multicast(Desktop)

            with ui.card():
                new_cast_devices = ui.input('Cast Devices', value=str(Desktop.cast_devices))
                new_cast_devices.tooltip('Click on MANAGE to enter devices for Multicast')
                new_cast_devices.on('focusout',
                                    lambda: update_attribute_by_name('Desktop','cast_devices',
                                                                                         new_cast_devices.value))
                ui.button('Manage', on_click=lambda: nice.cast_device_manage(Desktop, Netdevice))

            with ui.card():
                await nice.edit_protocol(Desktop)

            with ui.card():
                await nice.edit_artnet(Desktop)

            with ui.card():
                new_record = ui.checkbox(text='Record', value=False).bind_value(Desktop,'record')
                new_record.tooltip('Select if want to record cast')
                new_record_file = ui.input('File name').bind_value(Desktop,'output_file')
                new_record_file.tooltip('Provide file name for record, extension determine format eg: file.mp4')

    ui.separator().classes('mt-6')

    with ui.expansion('BUFFER', icon='grid_view', on_value_change=lambda: exp_edit_param.close()) \
            .classes('w-full'):
        if len(Desktop.frame_buffer) > 0:
            with ui.row():
                media_grid = ui.grid(columns=8)
                with media_grid:
                    for i in range(len(Desktop.frame_buffer)):
                        # put fixed size for preview
                        img = CV2Utils.resize_image(Desktop.frame_buffer[i], 640, 360)
                        img = Image.fromarray(img)
                        await light_box_image(i, img, '', '', Desktop, 'frame_buffer')
                with ui.carousel(animated=True, arrows=True, navigation=True).props('height=480px'):
                    await nice.generate_carousel(Desktop)

        else:
            with ui.card():
                ui.label('No image to show...').classes('animate-pulse')

    with ui.expansion('MULTICAST', icon='grid_view', on_value_change=lambda: exp_edit_param.close()) \
            .classes('w-full'):
        # columns number  = cast_x, number of cards = cast_x * cast_y
        if Desktop.multicast:
            with ui.row():
                await nice.multi_preview(Desktop)
                await nice.cast_devices_view(Desktop)
            if len(Desktop.cast_frame_buffer) > 0:
                with ui.grid(columns=Desktop.cast_x):
                    try:
                        for i in range(Desktop.cast_x * Desktop.cast_y):
                            # put fixed size for preview
                            img = CV2Utils.resize_image(Desktop.cast_frame_buffer[i], 640, 360)
                            img = Image.fromarray(img)
                            await light_box_image(i, img, i, '', Desktop, 'cast_frame_buffer')
                    except Exception as m_error:
                        main_logger.error(traceback.format_exc())
                        main_logger.error(f'An exception occurred: {m_error}')
            else:
                with ui.card():
                    ui.label('No frame captured yet...').style('background: red')
        else:
            with ui.card():
                ui.label('Multicast not set') \
                    .style('text-align:center; font-size: 150%; font-weight: 300') \
                    .classes('animate-pulse')

    with ui.footer():

        await net_view_button(show_only=False)

        async def display_windows():
            with ui.dialog() as dialog, ui.card():
                dialog.open()
                editor = ui.json_editor({'content': {'json': Desktop.windows_titles}})
                await editor.run_editor_method('updateProps', {'readOnly': True})
                await editor.run_editor_method(':expand', '[], relativePath => relativePath.length < 1')
                ui.button('Close', on_click=dialog.close, color='red')

        ui.button('Win TITLES', on_click=display_windows, color='bg-red-800').tooltip('View windows titles')
        ui.button('Fetch Win TITLES', on_click=grab_windows, color='bg-red-800').tooltip('Retrieve windows titles')


@ui.page('/Media')
async def main_page_media():
    """
    Media param page
    """
    ui.dark_mode(CastAPI.dark_mode)

    await apply_custom()

    await nice.head_menu(name='Media Params', target='/Media', icon='image')

    async def media_validate():
        # retrieve matrix setup from wled and set w/h
        if Media.wled:
            Media.scale_width, Media.scale_height = await Utils.get_wled_matrix_dimensions(Media.host)
        ui.navigate.reload()

    if str2bool(cfg_mgr.custom_config['animate_ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="assets/css/animate.min.css"/>
        """)

    columns_a = [
        {'name': 'rate', 'label': 'FPS', 'field': 'rate', 'align': 'left'},
        {'name': 'scale_width', 'label': 'W', 'field': 'scale_width'},
        {'name': 'scale_height', 'label': 'H', 'field': 'scale_height'}
    ]
    rows_a = [
        {'id': 0, 'rate': Media.rate, 'scale_width': Media.scale_width, 'scale_height': Media.scale_height}
    ]
    columns_b = [
        {'name': 'wled', 'label': 'WLED', 'field': 'wled', 'align': 'left'},
        {'name': 'host', 'label': 'IP', 'field': 'host'}
    ]
    rows_b = [
        {'id': 0, 'wled': Media.wled, 'host': Media.host}
    ]
    columns_c = [
        {'name': 'viinput', 'label': 'Input', 'field': 'viinput', 'align': 'left'},
        {'name': 'preview', 'label': 'Preview', 'field': 'preview'}
    ]
    rows_c = [
        {'id': 0, 'viinput': Media.viinput, 'preview': Media.preview}
    ]
    columns_d = [
        {'name': 'multicast', 'label': 'MultiCast', 'field': 'multicast', 'align': 'left'},
        {'name': 'matrix-x', 'label': 'H', 'field': 'matrix-x'},
        {'name': 'matrix-y', 'label': 'V', 'field': 'matrix-y'}
    ]
    rows_d = [
        {'id': 0, 'multicast': Media.multicast, 'matrix-x': Media.cast_x, 'matrix-y': Media.cast_y}
    ]
    media_exp_param = ui.expansion('Parameters', icon='settings', value=True)
    with media_exp_param.classes('w-full bg-sky-800'):

        with ui.row(wrap=False):
            await nice.cast_icon(Media)
            manage_cast_presets('Media', Media)

        with ui.row():
            ui.table(columns=columns_a, rows=rows_a).classes('w-60')
            ui.table(columns=columns_b, rows=rows_b).classes('w-60')
            ui.table(columns=columns_c, rows=rows_c).classes('w-60')
            ui.table(columns=columns_d, rows=rows_d).classes('w-60')

            with ui.grid(columns=2):
                ui.label('Protocol:')
                ui.label(Media.protocol)

                ui.label('Port:')
                ui.label(str(Media.port))

                ui.label('No of Packet:')
                ui.label(str(Media.retry_number))

    if str2bool(cfg_mgr.custom_config['animate_ui']):
        media_exp_edit_param_anim = Animate(ui.expansion, animation_name_in='backInDown', duration=1)
        media_exp_edit_param = media_exp_edit_param_anim.create_element()
    else:
        media_exp_edit_param = ui.expansion()

    media_exp_edit_param.text = 'Edit'
    media_exp_edit_param.props(add="icon='edit'")
    media_exp_edit_param.classes('w-full bg-sky-800')
    media_exp_edit_param.on_value_change(lambda: media_exp_param.close())

    with media_exp_edit_param:
        with ui.row():
            ui.icon('restore_page', color='blue', size='md') \
                .style('cursor: pointer').tooltip('Click to Validate/Refresh') \
                .on('click', lambda: media_validate())

            with ui.card():
                await nice.edit_rate_x_y(Media)

            with ui.card():
                new_viinput = ui.input('Input', value=str(Media.viinput))
                new_viinput.on('focusout', lambda: update_attribute_by_name('Media','viinput', new_viinput.value))
                new_viinput.tooltip('Enter desired input : e.g 0..n / file name  etc ...')
                new_preview = ui.checkbox('Preview')
                new_preview.bind_value(Media, 'preview')
                new_preview.tooltip('Show preview window')

            with ui.card():

                await nice.edit_ip(Media)

            with ui.card():

                await nice.edit_capture(Media)

            with ui.card():

                await nice.edit_multicast(Media)

            with ui.card():

                await nice.edit_protocol(Media)

            with ui.card():

                await nice.edit_artnet(Media)

            with ui.card():
                new_cast_devices = ui.input('Cast Devices', value=str(Media.cast_devices))
                new_cast_devices.tooltip('Click on MANAGE to enter devices for Multicast')
                new_cast_devices.on('focusout',
                                    lambda: update_attribute_by_name('Media','cast_devices',
                                                                                         new_cast_devices.value))
                ui.button('Manage', on_click=lambda: nice.cast_device_manage(Media, Netdevice))

    ui.separator().classes('mt-6')

    with ui.expansion('BUFFER', icon='grid_view', on_value_change=lambda: media_exp_edit_param.close()) \
            .classes('w-full'):
        if len(Media.frame_buffer) > 0:
            with ui.row():
                media_grid = ui.grid(columns=8)
                with media_grid:
                    for i in range(len(Media.frame_buffer)):
                        # put fixed size for preview
                        img = CV2Utils.resize_image(Media.frame_buffer[i], 640, 360)
                        img = Image.fromarray(img)
                        await light_box_image(i, img, '', '', Media, 'frame_buffer')
                with ui.carousel(animated=True, arrows=True, navigation=True).props('height=480px'):
                    await nice.generate_carousel(Media)

        else:
            with ui.card():
                ui.label('No image to show...').classes('animate-pulse')

    with ui.expansion('MULTICAST', icon='grid_view', on_value_change=lambda: media_exp_edit_param.close()) \
            .classes('w-full'):
        # columns number  = cast_x, number of cards = cast_x * cast_y
        if Media.multicast:
            with ui.row():
                await nice.multi_preview(Media)
                await nice.cast_devices_view(Media)
            if len(Media.cast_frame_buffer) > 0:
                with ui.grid(columns=Media.cast_x):
                    try:
                        for i in range(Media.cast_x * Media.cast_y):
                            # put fixed size for preview
                            img = CV2Utils.resize_image(Media.cast_frame_buffer[i], 640, 360)
                            img = Image.fromarray(img)
                            await light_box_image(i, img, i, '', Media, 'cast_frame_buffer')
                    except Exception as e:
                        main_logger.error(traceback.format_exc())
                        main_logger.error(f'An exception occurred: {e}')
            else:
                with ui.card():
                    ui.label('No frame captured yet...').style('background: red')
        else:
            with ui.card():
                ui.label('Multicast not set') \
                    .style('text-align:center; font-size: 150%; font-weight: 300') \
                    .classes('animate-pulse')

    ui.separator().classes('mt-6')

    with ui.footer():

        await net_view_button(show_only=False)

        await media_dev_view_page()

        ui.button('Run discovery', on_click=discovery_media_notify, color='bg-red-800')


@ui.page('/WLEDVideoSync')
async def splash_page():
    """
    Page displayed on the webview window
    :return:
    """
    ui.dark_mode(True)
    ui.image('media/intro.gif').classes('self-center').style('width: 50%')
    main = ui.button(
        'MAIN INTERFACE',
        on_click=lambda: (main.props('loading'), ui.navigate.to('/')),
    ).classes('self-center')
    ui.button('API', on_click=lambda: ui.navigate.to('/docs')).classes(
        'self-center'
    )


@ui.page('/ws/docs')
async def ws_page():
    """
    websocket docs page
    :return:
    """
    ui.label('WEBSOCKETS Doc').classes('self-center')
    doc_txt = ui.textarea('WE endpoints').style('width: 50%')
    doc_txt.value = ( '/ws: e.g: ws://localhost:8000/ws \n'
                      '/ws/docs: e.g: http://localhost:8000/ws/docs \n'
                      'communication type : Json for in/out \n'
                      'format : {"action":{"type":"xxx","param":{"yyy":"zzz"...}}} \n'
                      'example: \n'
                     '{"action":'
                     '{"type":"cast_image", '
                     '"param":{"image_number":0,"device_number":-1, "class_name":"Media"}}}'
                     )

    ws_modules=['Utils','Net','ImageUtils','CV2Utils']
    func_rows = ui.row()

    def fetch_main_module():
        with ui.dialog() as dialog_m, ui.card():
            dialog_m.open()
            ui.json_editor({'content': {'json': Utils.func_info(sys.modules[__name__])}}) \
                .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog_m.close, color='red')

    def fetch_all_modules():
        with ui.dialog() as dialog_a, ui.card():
            dialog_a.open()
            ui.json_editor({'content': {'json': Utils.func_info(globals()[item_th])}}) \
                    .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog_a.close, color='red')

    with func_rows:
        item_exp = ui.expansion('local', icon='info') \
            .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')
        with item_exp:
            ui.button('Functions', on_click=fetch_main_module, color='bg-red-800').tooltip('View func info')
        for item_th in ws_modules:
            item_exp = ui.expansion(item_th, icon='info') \
                .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')
            with item_exp:
                ui.button('Functions', on_click=fetch_all_modules, color='bg-red-800').tooltip('View func info')


@ui.page('/info')
async def info_page():
    """ simple cast info page from systray """
    if str2bool(cfg_mgr.custom_config['animate_ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="assets/css/animate.min.css"/>
        """)
    #if CastAPI.info_timer is None:
    CastAPI.info_timer = ui.timer(int(cfg_mgr.app_config['timer']), callback=info_timer_action)
    await cast_manage_page()


@ui.page('/DetailsInfo')
async def manage_info_page():
    """ Manage cast page from systray """
    await tabs_info_page()


@ui.page('/RunCharts')
async def manage_charts_page():
    """ Select chart """
    with ui.row(wrap=False).classes('w-full'):
        with ui.card().classes('w-1/3'):
            ui.button('Device', on_click=dev_stats_info_page)

        with ui.card().classes('w-1/3'):
            ui.button('Network', on_click=net_stats_info_page)

        with ui.card().classes('w-1/3'):
            ui.button('System', on_click=sys_stats_info_page)


@ui.page('/Fonts')
async def manage_font_page():

    ui.dark_mode(CastAPI.dark_mode)

    await apply_custom()

    from src.txt.fontsmanager import font_page

    await font_page()


@ui.page('/config_editor')
async def config_editor_page():
    """
    The NiceGUI page that hosts the configuration editor.
    """
    from src.gui.niceutils import head_menu
    from src.gui.config_page import create_config_page

    ui.dark_mode(CastAPI.dark_mode)
    await apply_custom()
    await head_menu(name='Config Editor', target='/config_editor', icon='settings')

    await create_config_page()


@ui.page('/Coldtype')
async def coldtype_test_page():

    ui.dark_mode(CastAPI.dark_mode)

    await apply_custom()

    def cold_run():
        cold = RUNColdtype()
        cold.start()

    ui.button('run Coldtype', on_click=cold_run).classes('self-center')

    print('end of coldtype page load')


@ui.page('/Pyeditor')
async def pyeditor_test_page():

    ui.dark_mode(CastAPI.dark_mode)

    await apply_custom()

    # Instantiate and run the editor
    editor_app = PythonEditor()
    await editor_app.setup_ui()

    print('end of pyeditor page load')


@ui.page('/ShutDown')
async def stop_app():

    ui.dark_mode(CastAPI.dark_mode)

    await apply_custom()

    ui.button('ShutDown', on_click=app.shutdown).classes('flex h-screen m-auto')


@ui.page(cast_center_url)
async def cast_center_page():
    await cast_app.setup_ui()

@ui.page('/Scheduler')
async def scheduler_page():
    ui.dark_mode(CastAPI.dark_mode)

    await apply_custom()
    await nice.head_menu(name='Scheduler', target='/Scheduler', icon='more_time')
    await scheduler_app.setup_ui()

    print('end of Scheduler page load')


@ui.page('/manage_cast/{thread_name}')
async def manage_single_cast_page(thread_name: str):
    """
    Creates a dedicated page to manage a single, specific cast thread.
    This page is accessed via a parameterized URL and displays the
    action panel for the given thread.
    """
    ui.dark_mode(CastAPI.dark_mode)
    await apply_custom()

    # Determine the class_name from the thread_name
    class_name = 'Desktop' if 'desktop' in thread_name.lower() else 'Media'

    # Fetch the latest information for all running casts
    info_data = (await util_casts_info(img=True))['t_info']

    # Generate the action panel for only the specified thread
    await nice.generate_actions_to_cast(class_name, [thread_name], action_to_casts, info_data, True)


@ui.page('/control_panel')
async def create_control_panel_page():
    ui.dark_mode(CastAPI.dark_mode)
    await apply_custom()

    # Generate the control panel
    await control_panel_page()


"""
helpers /Commons
"""

async def control_panel_page():
    """
    Row for Cast /Filters / info / Run / Close
    """
    # filters for Desktop / Media
    with ui.row().classes('self-center') as CastAPI.control_panel:
        # By default, hide the control panel if the video player is visible.
        # This can be overridden by the toggle button.
        if CastAPI.player:
            CastAPI.control_panel.bind_visibility_from(CastAPI.player, 'visible', backward=lambda v: not v)

        await nice.filters_data(Desktop)

        with ui.card().tight().classes('w-42'):
            with ui.column():

                # refreshable
                await cast_manage_page()
                # end refreshable

                ui.icon('info') \
                    .tooltip('Show details') \
                    .on('click', lambda: show_threads_info()) \
                    .classes('self-center') \
                    .style('cursor: pointer')
                with ui.row().classes('self-center'):
                    with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700'):
                        with ui.row():
                            ui.checkbox('') \
                                .bind_value(Desktop, 'preview_top', forward=lambda value: value) \
                                .tooltip('Preview always on TOP').classes('w-10')
                            ui.knob(640, min=8, max=1920, step=1, show_value=True) \
                                .bind_value(Desktop, 'preview_w') \
                                .tooltip('Preview size W').classes('w-10')
                            ui.knob(360, min=8, max=1080, step=1, show_value=True) \
                                .bind_value(Desktop, 'preview_h') \
                                .tooltip('Preview size H').classes('w-10')
                    with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700'):
                        with ui.row():
                            ui.knob(640, min=8, max=1920, step=1, show_value=True) \
                                .bind_value(Media, 'preview_w') \
                                .tooltip('Preview size W').classes('w-10')
                            ui.knob(360, min=8, max=1080, step=1, show_value=True) \
                                .bind_value(Media, 'preview_h') \
                                .tooltip('Preview size H').classes('w-10')
                            ui.checkbox('') \
                                .bind_value(Media, 'preview_top', forward=lambda value: value) \
                                .tooltip('Preview always on TOP').classes('w-10')

                # presets
                with ui.row().classes('self-center'):

                    manage_filter_presets('Desktop', Desktop)
                    manage_filter_presets('Media', Media)

                # refreshable
                with ui.expansion('Monitor', icon='query_stats').classes('self-center w-full'):
                    if str2bool(cfg_mgr.custom_config['system_stats']):
                        with ui.row().classes('self-center'):
                            frame_count = ui.number(prefix='F:').bind_value_from(CastAPI, 'total_frames')
                            frame_count.tooltip('TOTAL Frames')
                            frame_count.classes("w-20")
                            frame_count.props(remove='type=number', add='borderless')

                            total_reset_icon = ui.icon('restore')
                            total_reset_icon.style("cursor: pointer")
                            total_reset_icon.on('click', lambda: reset_total())

                            packet_count = ui.number(prefix='P:').bind_value_from(CastAPI, 'total_packets')
                            packet_count.tooltip('TOTAL DDP Packets')
                            packet_count.classes("w-25")
                            packet_count.props(remove='type=number', add='borderless')

                        ui.separator()

                        with ui.row().classes('self-center'):
                            cpu_count = ui.number(prefix='CPU%: ').bind_value_from(CastAPI, 'cpu')
                            cpu_count.classes("w-20")
                            cpu_count.props(remove='type=number', add='borderless')

                            ram_count = ui.number(prefix='RAM%: ').bind_value_from(CastAPI, 'ram')
                            ram_count.classes("w-20")
                            ram_count.props(remove='type=number', add='borderless')

                    if str2bool(cfg_mgr.custom_config['cpu_chart']):
                        await nice.create_cpu_chart(CastAPI)

        await nice.filters_data(Media)


async def animate_toggle(img):
    """ toggle animation """

    if str2bool(cfg_mgr.custom_config['animate_ui']):
        # put animation False
        cfg_mgr.custom_config['animate_ui'] = 'False'
        img.classes('animate__animated animate__hinge')
    else:
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="assets/css/animate.min.css"/>
        """)
        # put animation True
        cfg_mgr.custom_config['animate_ui'] = 'True'
        img.classes('animate__animated animate__rubberBand')

    ui.notify(f'Animate :{cfg_mgr.custom_config["animate_ui"]}')

    main_logger.debug(f'Animate :{cfg_mgr.custom_config["animate_ui"]}')


async def open_webview_page(thread_name: str) -> None:
    """
    Opens a new native webview or browser window (depend on native_ui) for a specific cast's management page.
    This function is safely called from a background thread.
    """
    from src.gui.wledtray import WLEDVideoSync_gui, server_port
    import webbrowser

    url = f"http://localhost:{server_port}/manage_cast/{thread_name}"
    title = f"WLEDVideoSync - Manage: {thread_name}"

    main_logger.info(f"Requesting new webview or browser window for: {url}")
    if str2bool(cfg_mgr.app_config['native_ui']):
        WLEDVideoSync_gui.open_webview(url=url, title=title, width=440, height=580)
    else:
        webbrowser.open_new(url=url)

async def grab_windows():
    """Retrieves and displays window titles.

    This function retrieves all window titles and displays a notification.
    """

    ui.notification('Retrieved all windows information', close_button=True, timeout=3)
    Desktop.windows_titles = await windows_titles()

async def reset_total():
    """ reset frames / packets total values for Media and Desktop """
    Media.reset_total = True
    Desktop.reset_total = True
    #  instruct first cast to reset values
    if len(Media.cast_names) != 0:
        result = action_to_thread(class_name='Media',
                                        cast_name=Media.cast_names[0],
                                        action='reset',
                                        clear=False,
                                        execute=True
                                        )
        ui.notify(result)

    if len(Desktop.cast_names) != 0:
        result = action_to_thread(class_name='Desktop',
                                        cast_name=Desktop.cast_names[0],
                                        action='reset',
                                        clear=False,
                                        execute=True
                                        )
        ui.notify(result)

    ui.notify('Reset Total')


def charts_select():
    """
    select charts
    :return:
    """
    if os.path.isfile(select_chart_exe()):
        CastAPI.charts_row.set_visibility(True)
    else:
        ui.notify('No charts executable', type='warning')

async def font_select():
    """
    Font Page
    :return:
    """

    with ui.dialog() as font_dialog:
        font_dialog.open()
        with ui.card().classes('w-full'):
            await manage_font_page()
            ui.button('close', on_click=font_dialog.close).classes('self-center')


def dev_stats_info_page():
    """ devices charts """

    dev_ip = ['--dev_ip']
    ips_list = []
    if Desktop.host != '127.0.0.1':
        ips_list.append(Desktop.host)
    if Media.host != '127.0.0.1':
        ips_list.append(Media.host)

    ips_list.extend(
        Desktop.cast_devices[i][1] for i in range(len(Desktop.cast_devices))
    )
    ips_list.extend(
        Media.cast_devices[i][1] for i in range(len(Media.cast_devices))
    )
    
    if not ips_list:
        ips_list.append('127.0.0.1')

    ips_list = [','.join(ips_list)]

    dark = ['--dark'] if CastAPI.dark_mode is True else []
    # run chart on its own process
    Popen(["devstats"] + dev_ip + ips_list + dark,
          executable=select_chart_exe())

    main_logger.debug('Run Device(s) Charts')
    CastAPI.charts_row.set_visibility(False)


def net_stats_info_page():
    """ network charts """

    dark = ['--dark'] if CastAPI.dark_mode is True else []
    Popen(["netstats"] + dark,
          executable=select_chart_exe())

    CastAPI.charts_row.set_visibility(False)
    main_logger.debug('Run Network Chart')


def sys_stats_info_page():
    """ system charts """

    dark = ['--dark'] if CastAPI.dark_mode is True else []
    Popen(["sysstats"] + dark,
          executable=select_chart_exe())

    CastAPI.charts_row.set_visibility(False)
    main_logger.debug('Run System Charts')


def select_chart_exe():
    return cfg_mgr.app_root_path(cfg_mgr.app_config['charts_exe'])


async def cast_manage_page():
    """
    Cast parameters on the root page /
    :return:
    """

    with ui.card().tight().classes('self-center'):
        with ui.row():
            with ui.column(align_items='start', wrap=False):
                if Desktop.count > 0:
                    my_col = 'red'
                elif Desktop.stopcast:
                    my_col = 'yellow'
                else:
                    my_col = 'green'
                CastAPI.desktop_cast = ui.icon('cast', size='xl', color=my_col)
                CastAPI.desktop_cast.on('click', lambda: auth_cast(Desktop))
                CastAPI.desktop_cast_run = ui.button(icon='touch_app', on_click=lambda: init_cast(Desktop)) \
                    .classes('shadow-lg') \
                    .props(add='push size="md"') \
                    .tooltip('Initiate Desktop Cast')
                if Desktop.stopcast is True:
                    CastAPI.desktop_cast_run.set_visibility(False)

            ui.icon('stop_screen_share', size='xs', color='red') \
                .style('cursor: pointer') \
                .on('click', lambda: cast_stop(Desktop)).tooltip('Stop Cast')

            if str2bool(cfg_mgr.custom_config['animate_ui']):
                animated_card = Animate(ui.card, animation_name_in="fadeInUp", duration=2)
                card = animated_card.create_element()
            else:
                card = ui.card()
            card.classes('bg-red-900')

            with card:
                ui.label(' Running Cast(s) ').classes('self-center').style("color: yellow; background: purple")
                with ui.row():
                    desktop_count = ui.number(prefix='Desktop:').bind_value_from(Desktop, 'count')
                    desktop_count.classes("w-20")
                    desktop_count.props(remove='type=number', add='borderless')
                    media_count = ui.number(prefix='Media: ').bind_value_from(Media, 'count')
                    media_count.classes("w-20")
                    media_count.props(remove='type=number', add='borderless')

            ui.icon('stop_screen_share', size='xs', color='red') \
                .style('cursor: pointer') \
                .on('click', lambda: cast_stop(Media)).tooltip('Stop Cast')

            with ui.column(align_items='end', wrap=False):
                if Media.count > 0:
                    my_col = 'red'
                elif Media.stopcast:
                    my_col = 'yellow'
                else:
                    my_col = 'green'
                CastAPI.media_cast = ui.icon('cast', size='xl', color=my_col)
                CastAPI.media_cast.on('click', lambda: auth_cast(Media))
                CastAPI.media_cast_run = ui.button(icon='touch_app', on_click=lambda: init_cast(Media)) \
                    .classes('shadow-lg') \
                    .props(add='push size="md"') \
                    .tooltip('Initiate Media Cast')
                if Media.stopcast is True:
                    CastAPI.media_cast_run.set_visibility(False)


async def tabs_info_page():
    """ generate action/info page split by classes and show all running casts """

    # grab data
    info_data = await util_casts_info(img=True)
    # take only info data key
    info_data = info_data['t_info']
    # split desktop / media by using content of thread name
    desktop_threads = []
    media_threads = []
    for item in info_data:
        if 't_desktop_cast' in item:
            desktop_threads.append(item)
        elif 't_media_cast' in item:
            media_threads.append(item)

    """
    Tabs
    """

    if str2bool(cfg_mgr.custom_config['animate_ui']):
        # Add Animate.css to the HTML head
        ui.add_head_html("""
        <link rel="stylesheet" href="assets/css/animate.min.css"/>
        """)
        tabs_anim = Animate(ui.tabs, animation_name_in='backInDown', duration=1)
        tabs = tabs_anim.create_element()
    else:
        tabs = ui.tabs()

    tabs.classes('w-full')
    with tabs:
        p_desktop = ui.tab('Desktop', icon='computer').classes('bg-slate-400')
        p_media = ui.tab('Media', icon='image').classes('bg-slate-400')

        if Desktop.count > Media.count:
            tab_to_show = p_desktop
        elif Desktop.count < Media.count:
            tab_to_show = p_media
        else:
            tab_to_show = ''

    with (ui.tab_panels(tabs, value=tab_to_show).classes('w-full')):

        with ui.tab_panel(p_desktop):
            if not desktop_threads:
                ui.label('No CAST').classes('animate-pulse') \
                    .style('text-align:center; font-size: 150%; font-weight: 300')
            else:
                # create Graph
                graph_data = ''
                for item in desktop_threads:
                    t_id = info_data[item]["data"]["tid"]
                    t_name = item.replace(' ', '_').replace('(', '').replace(')', '')
                    graph_data += "WLEDVideoSync --> " + "|" + str(t_id) + "|" + t_name + "\n"
                with ui.row():
                    with ui.card():
                        ui.mermaid('''
                        graph LR;''' + graph_data + '''
                        ''')
                    await nice.generate_actions_to_cast('Desktop', desktop_threads, action_to_casts, info_data)

        with ui.tab_panel(p_media):
            if not media_threads:
                ui.label('No CAST').classes('animate-pulse') \
                    .style('text-align:center; font-size: 150%; font-weight: 300')
            else:
                # create Graph
                graph_data = ''
                for item in media_threads:
                    t_id = info_data[item]["data"]["tid"]
                    t_name = item.replace(' ', '_').replace('(', '').replace(')', '')
                    graph_data += "WLEDVideoSync --> " + "|" + str(t_id) + "|" + t_name + "\n"
                with ui.row():
                    with ui.card():
                        ui.mermaid('''
                        graph LR;''' + graph_data + '''
                        ''')
                    await nice.generate_actions_to_cast('Media', media_threads, action_to_casts, info_data)


async def action_to_casts(class_name, cast_name, action, params, clear, execute, data=None, exp_item=None):
    """ execute action from icon click and display a message """

    def valid_check():
        if circular.value:
            reverse.value= False
            random.value = False
            pause.value = False
            return 'circular'
        if reverse.value:
            circular.value = False
            random.value = False
            pause.value = False
            return 'reverse'
        if random.value:
            circular.value = False
            reverse.value = False
            pause.value = False
            return 'random'
        if pause.value:
            circular.value = False
            reverse.value = False
            random.value = False
            return 'pause'

    def valid_swap():
        type_effect = valid_check()
        if type_effect is None:
            # stop effects
            action_to_thread(class_name, cast_name, action, 'stop', clear, execute=True)
            ui.notify('Effect stop & Reset to initial')
        else:
            ui.notify(f'Initiate effect: {type_effect}')
            action_to_thread(
                class_name,
                cast_name,
                action,
                f'{type_effect},{int(new_delay.value)}',
                clear,
                execute=True,
            )

    def valid_ip():
        if new_ip.value == '127.0.0.1' or Utils.check_ip_alive(new_ip.value, ping=True):
            # put to loopback if cast(s) with same IP already exist, and we do not want multi
            if multi.value is False:
                name = None
                for thread_name, thread_info in data.items():
                    cast_type = thread_info['data'].get('cast_type', 'unknown')  # Default to 'unknown' if not specified
                    if cast_type == 'CASTDesktop':
                        name = 'Desktop'
                    elif cast_type == 'CASTMedia':
                        name = 'Media'
                    devices = thread_info['data'].get('devices', [])
                    multicast = thread_info['data'].get('multicast', True)  # Default to True if not specified
                    # put new IP and action in wait mode
                    if new_ip.value in devices and not multicast:
                        data[thread_name]['data']['devices'][0] = '127.0.0.1'
                        action_to_thread(name, thread_name, action, '127.0.0.1', clear, execute=False)
            # put new IP and execute action
            data[cast_name]['data']['devices'][0] = new_ip.value
            action_to_thread(class_name, cast_name, action, new_ip.value, clear, execute=True)
            ui.notification('IP address applied', type='positive', position='center', timeout=2)
        else:
            ui.notification('Bad IP address or not reachable', type='negative', position='center', timeout=2)

    if action == 'host':
        with ui.dialog() as dialog, ui.card() as ip_card:
            dialog.open()
            ip_card.classes('w-full')
            with ui.row():
                new_ip = ui.input('IP',placeholder='Enter new IP address', value='127.0.0.1')
                multi = ui.checkbox('allow multiple', value=False)
                multi.tooltip('Check to let Cast(s) with same Device/IP to continue stream')
            with ui.row():
                ui.button('OK', on_click=valid_ip)
                ui.button('Close', color='red', on_click=dialog.close)

        ui.notification(f'Change IP address for  {cast_name}...', type='info', position='top', timeout=2)

    elif action == 'multicast':
        with ui.dialog() as dialog, ui.card() as ip_card:
            dialog.open()
            ip_card.classes('w-full')
            with ui.row():
                new_delay = ui.number('Delay',
                                      placeholder='Delay in ms',
                                      value=1000,
                                      min=1,
                                      max=100000,
                                      precision=0)
                new_delay.tooltip('how long between swapping')
                circular = ui.checkbox('circular', value=False, on_change=valid_check)
                circular.tooltip('Swap IP one by one (circular)')
                reverse = ui.checkbox('reverse', value=False, on_change=valid_check)
                reverse.tooltip('Swap IP one by one in reverse order (reverse)')
                random = ui.checkbox('random', value=False, on_change=valid_check)
                random.tooltip('Swap IP randomly (random)')
                pause = ui.checkbox('Pause random', value=False, on_change=valid_check)
                pause.tooltip('Pause Cast/IP randomly (pause)')

            with ui.row():
                ui.button('OK', on_click=valid_swap).tooltip('Validate, if nothing checked stop and set IP to initial')
                ui.button('Close', color='red', on_click=dialog.close)

    else:

        action_to_thread(class_name, cast_name, action, params, clear, execute)

        if action == 'stop':
            exp_item.close()
            ui.notification(f'Stopping {cast_name}...', type='warning', position='center', timeout=1)
            exp_item.delete()
            del data[cast_name]
        elif action == 'shot':
            ui.notification(f'Saving image to buffer for  {cast_name}...', type='positive', timeout=1)
        elif action == 'close-preview':
            ui.notification(f'Preview window terminated for  {cast_name}...', type='info', timeout=1)
        else:
            ui.notification(f'Initiate {action} with params {params} for {cast_name}...', type='info', timeout=1)


async def show_threads_info():
    """ show all info from running cast """

    dialog = ui.dialog().props(add='transition-show="slide-down" transition-hide="slide-up"')
    with dialog, ui.card():
        cast_info = await util_casts_info()
        await ui.json_editor({'content': {'json': cast_info}}) \
            .run_editor_method('updateProps', {'readOnly': True})
        ui.button('Close', on_click=dialog.close, color='red')
        dialog.open()


async def root_timer_action():
    """
    timer action occur only when root page is active /
    :return:
    """

    await nice.sync_button(CastAPI, Media)

    await nice.cast_manage(CastAPI, Desktop, Media)

    if str2bool(cfg_mgr.custom_config['system_stats']):
        await nice.system_stats(CastAPI, Desktop, Media)

    """
    if CastAPI.loop is None:
        CastAPI.loop=asyncio.get_running_loop()
    """

async def info_timer_action():
    """
    timer action occur only when info page is active '/info'
    :return:
    """

    await nice.cast_manage(CastAPI, Desktop, Media)


async def player_timer_action():
    """
    timer action occur when player is displayed
    :return:
    """
    await nice.sync_button(CastAPI, Media)


async def cast_to_wled(class_obj, image_number):
    """
    Cast to wled from GUI
    used on the buffer images
    """

    if not class_obj.wled:
        ui.notify('Not a WLED device', type='negative', position='center')
        return

    if Utils.check_ip_alive(class_obj.host):
        ui.notify(f'Cast to device : {class_obj.host}')
        if 'Desktop' in str(type(class_obj)):
            class_name = 'Desktop'
        elif 'Media' in str(type(class_obj)):
            class_name = 'Media'
        else:
            class_name = 'unknown'

        # select buffer for image to send
        buffer_name = 'multicast' if class_obj.multicast else 'buffer'
        # send image
        cast_image(
            image_number=image_number,
            device_number=-1,
            class_name=class_name,
            fps_number=25,
            duration_number=1000,
            retry_number=1,
            buffer_name=buffer_name
        )
    else:
        main_logger.warning('Device do not accept connection to port 80')
        ui.notify('Device do not accept connection to port 80', type='warning')


async def discovery_media_notify():
    """ Call Run OS Media discovery by av """

    ui.notification('MEDIA Discovery process on go ... let it finish',
                    close_button=True,
                    type='warning',
                    timeout=3)
    await Utils.dev_list_update()


async def init_cast(class_obj):
    """
    Run the cast and refresh the cast view
    :param class_obj:
    :return:
    """
    class_obj.cast(shared_buffer=t_data_buffer)
    await nice.cast_manage(CastAPI, Desktop, Media)
    main_logger.info(f'Run Cast for {str(class_obj)}')
    # ui.notify(f'Cast initiated for :{str(class_obj)}')


async def cast_stop(class_obj):
    """ Stop cast """

    class_obj.stopcast = True
    # ui.notify(f'Cast(s) stopped and blocked for : {class_obj}', position='center', type='info', close_button=True)
    await nice.cast_manage(CastAPI, Desktop, Media)
    main_logger.info(f' Stop Cast for {str(class_obj)}')


async def auth_cast(class_obj):
    """ Authorized cast """

    class_obj.stopcast = False
    # ui.notify(f'Cast(s) Authorized for : {class_obj}', position='center', type='info', close_button=True)
    await nice.cast_manage(CastAPI, Desktop, Media)
    main_logger.info(f' Cast auth. for {str(class_obj)}')


async def light_box_image(index, image, txt1, txt2, class_obj, buffer):
    """
    Provide basic 'lightbox' effect for image
    :param buffer:
    :param class_obj:
    :param index:
    :param image:
    :param txt1:
    :param txt2:
    :return:
    """
    with ui.card():
        try:
            with ui.image(image):
                if txt1 != '' or txt2 != '':
                    ui.label(txt1).classes('absolute-bottom text-subtitle2 text-center')
                    ui.label(txt2).classes('absolute-bottom text-subtitle2 text-center')
                ui.label(str(index))

            dialog = ui.dialog().style('width: 800px')
            with dialog:
                ui.label(str(index)) \
                    .tailwind.font_weight('extrabold').text_color('red-600').background_color('orange-200')
                with ui.interactive_image(image):
                    with ui.row().classes('absolute top-0 left-0 m-2'):
                        ui.button(on_click=lambda: cast_to_wled(class_obj, index), icon='cast') \
                            .props('flat fab color=white') \
                            .tooltip('Cast to WLED')
                        ui.button(on_click=lambda: (ui.notify('saving...'),
                                                    CV2Utils.save_image(class_obj, buffer, index, False)),
                                  icon='save') \
                            .props('flat fab color=white') \
                            .tooltip('Save Image')
                        ui.button(on_click=lambda: (ui.notify('saving...'),
                                                    CV2Utils.save_image(class_obj, buffer, index, True)),
                                  icon='text_format') \
                            .props('flat fab color=white') \
                            .tooltip('Save Image as Ascii ART')

                    ui.label(str(index)).classes('absolute-bottom text-subtitle2 text-center').style('background: red')
                ui.button('Close', on_click=dialog.close, color='red')
            ui.button('', icon='preview', on_click=dialog.open, color='bg-red-800').tooltip('View image')

        except Exception as im_error:
            main_logger.error(traceback.format_exc())
            main_logger.error(f'An exception occurred: {im_error}')


# do not use if __name__ in {"__main__", "__mp_main__"}, made code reload with cpu_bound !!!!
if __name__ == "__main__":
    from nicegui import app

    print('start nicegui')

    # store fake server port info for others processes
    port = 8080
    with shelve.open(WLED_PID_TMP_FILE) as proc_file:
        proc_file["server_port"] = port
        proc_file["sc_area"] = []
        proc_file["media"] = None

    app.add_static_files('/assets', cfg_mgr.app_root_path('assets'))
    app.add_media_files('/media', cfg_mgr.app_root_path('media'))
    app.add_static_files('/log', cfg_mgr.app_root_path('log'))
    app.add_static_files('/config', cfg_mgr.app_root_path('config'))
    app.add_static_files('/tmp', cfg_mgr.app_root_path('tmp'))
    app.add_static_files('/xtra', cfg_mgr.app_root_path('xtra'))
    app.on_startup(init_actions)

    ui.run(reload=False, fastapi_docs=True)

    print('end nicegui')