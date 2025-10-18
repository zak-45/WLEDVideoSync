import os
import traceback
from subprocess import Popen

from nicegui import ui
from str2bool import str2bool

from configmanager import cfg_mgr, NATIVE_UI
from mainapp import main_logger, Desktop, Media, CastAPI, manage_font_page, t_data_buffer
from src.api.api import action_to_thread, util_casts_info, cast_image
from src.gui import niceutils as nice
from src.gui.presets import manage_filter_presets
from src.utl.cv2utils import CV2Utils
from src.utl.winutil import windows_titles
from src.utl.utils import CASTUtils as Utils
from src.gui.niceutils import AnimatedElement as Animate

"""
helpers /Commons main app pages
"""

async def control_panel_page():
    """
    Row for Cast /Filters / info / Run / Close
    """
    # filters for Desktop / Media
    with ui.row().classes('self-center') as CastAPI.control_panel:
        # By default, hide the control panel if the video player is visible.
        # This can be overridden by the toggle button.
        CastAPI.control_panel.set_visibility(True)
        if CastAPI.player:
            CastAPI.control_panel.bind_visibility_from(CastAPI.player, 'visible', backward=lambda v: not v)

        await nice.filters_data(Desktop)

        with ui.card().tight().classes('w-106'):
            with ui.column().classes('self-center'):

                # refreshable
                await cast_manage_page()
                # end refreshable

                ui.icon('info') \
                    .tooltip('Show details') \
                    .on('click', show_threads_info) \
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


async def open_webview_cast_page(thread_name: str) -> None:
    """
    Opens a new native webview or browser window (depend on native_ui) for a specific cast's management page.
    This function is safely called from a background thread.
    """
    from src.gui.wledtray import WLEDVideoSync_gui, server_port
    import webbrowser

    url = f"http://localhost:{server_port}/manage_cast/{thread_name}"
    main_logger.info(f"Requesting new webview or browser window for: {url}")

    if NATIVE_UI:
        title = f"WLEDVideoSync - Manage: {thread_name}"
        WLEDVideoSync_gui.open_webview(url=url, title=title, width=440, height=580)
    else:
        webbrowser.open_new(url=url)


async def open_webview_help_page():
    """
    Opens a new native webview or browser window (depend on native_ui) to provide help on keys.
    This function is safely called from a background thread.
    """
    from src.gui.wledtray import WLEDVideoSync_gui, server_port
    import webbrowser

    url = f"http://localhost:{server_port}/preview_help"
    main_logger.info(f"Requesting new webview or browser window for: {url}")

    if NATIVE_UI:
        title = "WLEDVideoSync - HELP Preview"
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
        with ui.row(wrap=True):
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
                if Desktop.stopcast:
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
                if Media.stopcast:
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
            reverse.value = False
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
        return None

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
                new_ip = ui.input('IP', placeholder='Enter new IP address', value='127.0.0.1')
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
                ui.label(str(index)).classes('font-extrabold text-red-600 bg-orange-200')
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

