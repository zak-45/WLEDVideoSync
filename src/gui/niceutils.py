"""
# a: zak-45
# d: 25/08/2024
# v: 1.0.0
#
# niceutils
# This file serves as a collection of utility functions and classes
# specifically designed to build and manage user interface components using the NiceGUI framework.
# It includes functions for creating and providing reusable UI elements and logic for various parts of the application,
# such as displaying system stats, managing cast devices, handling media information, and providing file picking
# capabilities.
#
#          NiceGUI utilities
#
# used by CastAPI mainly
#
"""
import psutil
import logging

from fastapi.openapi.utils import get_openapi
from nicegui import ui, events, run, app
from datetime import datetime

from str2bool import str2bool
from asyncio import create_task
from pytubefix import Search
from PIL import Image
from pathlib import Path
from typing import Optional

from src.txt.fontsmanager import FontSetApplication
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils
from src.utl.cv2utils import VideoThumbnailExtractor

from configmanager import cfg_mgr, PLATFORM, LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.nice')
nice_logger = logger_manager.logger

# Define a factory function to create a wheel event handler for a given slider
def create_wheel_handler(slider):
    """Creates a wheel event handler for a slider.

    This factory function generates an event handler that allows controlling
    a slider's value using the mouse wheel.

    Args:
        slider: The slider widget to control.

    Returns:
        function: The wheel event handler function.
    """

    # Define a function to round values based on the slider's step size
    def round_to_step(value, step):
        return round(value / step) * step

    def on_wheel(event):
        # Adjust the slider value based on the wheel movement and step size
        delta = event.args.get('deltaY', 0)
        step = slider.props['step']
        new_value = slider.value + (-step if delta > 0 else step)  # Adjusting direction as per deltaY value
        # Round the new value to the nearest step
        new_value = round_to_step(new_value, step)
        # Ensure the new value is within the slider's range
        min_value = slider.props['min']
        max_value = slider.props['max']
        slider.value = max(min_value, min(max_value, new_value))
    return on_wheel

async def system_stats(CastAPI, Desktop, Media):
    """Collects and displays system statistics.

    This function retrieves CPU and memory usage, updates a CPU usage chart
    if enabled, and displays notifications for high resource utilization.

    Args:
        CastAPI: The CastAPI instance.
        Desktop: The Desktop instance.
        Media: The Media instance.
    """

    CastAPI.cpu = psutil.cpu_percent(interval=1, percpu=False)
    CastAPI.ram = psutil.virtual_memory().percent
    CastAPI.total_packet = Desktop.total_packet + Media.total_packet
    CastAPI.total_frame = Desktop.total_frame + Media.total_frame

    if str2bool(cfg_mgr.custom_config['cpu_chart']) and CastAPI.cpu_chart is not None:
        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")
    
        CastAPI.cpu_chart.options['series'][0]['data'].append(CastAPI.cpu)
        CastAPI.cpu_chart.options['xAxis']['data'].append(date_time_str)
    
        CastAPI.cpu_chart.update()

    if CastAPI.cpu >= 75:
        ui.notify('High CPU utilization', type='negative', close_button=True)
    if CastAPI.ram >= 95:
        ui.notify('High Memory utilization', type='negative', close_button=True)


async def discovery_net_notify():
    """ Call Run zero conf net discovery """
    from mainapp import Netdevice
    ui.notification('NET Discovery process on go ... let it finish',
                close_button=True,
                type='warning',
                timeout=6)
    await run.io_bound(Netdevice.discover)


async def net_view_button(show_only: bool = True):
    """
    Display network devices into the Json Editor and create  ui.button if requested
    :return:
    """
    from mainapp import Netdevice
    def fetch_net():
        with ui.dialog() as dialog, ui.card():
            dialog.open()
            ui.json_editor({'content': {'json': Netdevice.http_devices}}) \
                .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog.close, color='red')

    if not show_only:
        # create button
        ui.button('Net devices', on_click=fetch_net, color='bg-red-800').tooltip('View network devices')
    else:
        # display net devices
        fetch_net()

async def animate_wled_image(CastAPI, visible):
    """ toggle main image animation """

    if visible:
        CastAPI.w_image.classes(add='animate__flipOutX', remove='animate__flipInX')
        ui.timer(0.4, lambda: CastAPI.w_image.set_visibility(False), once=True)
        # CastAPI.w_image.set_visibility(False)
    else:
        CastAPI.w_image.classes(add='animate__flipInX', remove='animate__flipOutX')
        CastAPI.w_image.set_visibility(True)


async def head_menu(name, target, icon):
    """Creates and displays a header with navigation links.

    This function generates a header element containing a title, icon, and
    navigation buttons for different sections of the application.

    Args:
        name (str): The name to display in the header.
        target (str): The target URL for the header link.
        icon (str): The name of the icon to display.
    """

    with ui.header(bordered=True, elevated=True).classes('items-center shadow-lg'):
        ui.link(name, target=target).classes('text-white text-lg font-medium')
        ui.icon(icon)
        # Create buttons
        if name != 'Main':
            root_page_url = Utils.root_page()
            if root_page_url == '/Cast-Center':
                go_to_url = '/main'
            else:
                go_to_url = '/'
            ui.button('Main', on_click=lambda: ui.navigate.to(go_to_url), icon='home')
        if name != 'Manage':
            ui.button('Manage', on_click=lambda: ui.navigate.to('/Manage'), icon='video_settings')
        if name != 'Desktop Params':
            ui.button('Desktop Params', on_click=lambda: ui.navigate.to('/Desktop'), icon='computer')
        if name != 'Media Params':
            ui.button('Media Params', on_click=lambda: ui.navigate.to('/Media'), icon='image')
        if name != 'Scheduler':
            ui.button('Scheduler', on_click=lambda: ui.navigate.to('/Scheduler'), icon='more_time')
        if str2bool(cfg_mgr.app_config['fastapi_docs']):
            ui.button('API', on_click=lambda: ui.navigate.to('/docs', new_tab=True), icon='api')
        ui.icon('info', size='sm').on('click', lambda: app_info()).style('cursor:pointer')


def app_info():
    """ display app , compile version """

    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.compile_info()}}) \
            .run_editor_method('updateProps', {'readOnly': True})


async def sync_button(CastAPI, Media):
    """Updates the appearance of synchronization buttons.

    This function manages the visual state of synchronization buttons based
    on the current synchronization status and type.

    Args:
        CastAPI: The CastAPI instance.
        Media: The Media instance.
    """

    if Media.cast_sync is True:
        # VSYNC
        CastAPI.media_button_sync.classes('animate-pulse')
        CastAPI.media_button_sync.props(add="color='gray'")
        if CastAPI.last_type_sync == 'player':
            CastAPI.media_button_sync.props(add="color='red'")
            CastAPI.media_button_sync.text = Media.sync_to_time
        # TSYNC
        CastAPI.slider_button_sync.classes('animate-pulse')
        CastAPI.slider_button_sync.props(add="color='gray'")
        if CastAPI.last_type_sync == 'slider':
            CastAPI.slider_button_sync.props(add="color='red'")
            CastAPI.slider_button_sync.text = Media.sync_to_time

    elif Media.cast_sync is False and CastAPI.type_sync != 'none':
        CastAPI.media_button_sync.props(add="color=green")
        CastAPI.media_button_sync.classes(remove="animate-pulse")
        CastAPI.media_button_sync.text = "VSYNC"
        CastAPI.media_button_sync.update()
        CastAPI.slider_button_sync.props(add="color=green")
        CastAPI.slider_button_sync.classes(remove="animate-pulse")
        CastAPI.slider_button_sync.text = "TSYNC"
        CastAPI.slider_button_sync.update()
        CastAPI.type_sync = 'none'


async def cast_manage(CastAPI, Desktop, Media):
    """Manages the visual state of cast buttons.

    This function updates the appearance of cast buttons based on the
    current casting status and availability.

    Args:
        CastAPI: The CastAPI instance.
        Desktop: The Desktop instance.
        Media: The Media instance.
    """

    if Desktop.count > 0:
        CastAPI.desktop_cast.props(add="color=red")
        CastAPI.desktop_cast.classes(add="animate-pulse")
    elif Desktop.stopcast is True:
        CastAPI.desktop_cast.props(add="color=yellow")
        CastAPI.desktop_cast.style(add='cursor: pointer')
        CastAPI.desktop_cast_run.set_visibility(False)
        CastAPI.desktop_cast.classes(remove="animate-pulse")
    else:
        CastAPI.desktop_cast.props(add="color=green")
        CastAPI.desktop_cast.style(remove='cursor: pointer')
        CastAPI.desktop_cast.classes(remove="animate-pulse")
    if Desktop.stopcast is False:
        CastAPI.desktop_cast_run.set_visibility(True)
        CastAPI.desktop_cast.style(remove='cursor: pointer')

    if Media.count > 0:
        CastAPI.media_cast.props(add="color=red")
        CastAPI.media_cast.style(remove='cursor: pointer')
        CastAPI.media_cast.classes(add="animate-pulse")
    elif Media.stopcast is True:
        CastAPI.media_cast.props(add="color=yellow")
        CastAPI.media_cast.style(add='cursor: pointer')
        CastAPI.media_cast.classes(remove="animate-pulse")
        CastAPI.media_cast_run.set_visibility(False)
    else:
        CastAPI.media_cast.props(add="color=green")
        CastAPI.media_cast.style(remove='cursor: pointer')
        CastAPI.media_cast.classes(remove="animate-pulse")
    if Media.stopcast is False:
        CastAPI.media_cast_run.set_visibility(True)
        CastAPI.media_cast.style(remove='cursor: pointer')


async def cast_icon(class_obj):
    """
    refresh Icon color on '/Desktop' and '/Media' pages
    :param class_obj:
    :return:
    """

    def upd_value():
        class_obj.stopcast = False
        my_icon.classes(remove='animate-pulse')
        ui.notify('Cast allowed', position='center', close_button=True, type='positive')

    cast_col = 'green' if class_obj.stopcast is False else 'yellow'
    my_icon = ui.icon('cast_connected', size='sm', color=cast_col) \
        .style('cursor: pointer') \
        .tooltip('Click to authorize') \
        .on('click', lambda: (my_icon.props(add='color=green'), upd_value())) \
        .classes('animate-pulse')


async def filters_data(class_obj):
    """Creates and displays image filter controls.

    This function generates UI elements for adjusting image filters and
    effects, such as flip, pixelation, gamma, color balance, saturation,
    brightness, contrast, sharpen, and auto brightness/contrast.

    Args:
        class_obj: The class instance to bind the filter values to.
    """

    #  Filters for Media/Desktop
    with (ui.card().classes('text-sm shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700')):
        ui.label(f'Filters/Effects {type(class_obj).__name__}')
        with ui.row().classes('w-44'):
            flip_img = ui.checkbox('Flip')
            flip_img.bind_value(class_obj, 'flip').classes('w-20')
            flip_img.tooltip('Flip Cast image')
            flip_number = ui.number('type', min=0, max=1).classes('w-20')
            flip_number.bind_value(class_obj, 'flip_vh', forward=lambda value: int(value or 0))
            flip_number.tooltip('Flip Type 0:H / 1:V ')
            px_w = ui.number('W', min=1, max=1920).classes('w-20')
            px_w.bind_value(class_obj, 'pixel_w', forward=lambda value: int(value or 8))
            px_w.tooltip('Pixel art Width Preview')
            px_h = ui.number('H', min=1, max=1080).classes('w-20')
            px_h.bind_value(class_obj, 'pixel_h', forward=lambda value: int(value or 8))
            px_h.tooltip('Pixel art Height Preview')
            with ui.row().classes('w-44').style('justify-content: flex-end'):
                ui.label('gamma')
                gamma_slider = ui.slider(min=0.01, max=4, step=0.01).props('label-always')
                gamma_slider.on('wheel', create_wheel_handler(gamma_slider))
                gamma_slider.bind_value(class_obj, 'gamma')

            with ui.column(wrap=True):
                with ui.row():
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-red') \
                            .bind_value(class_obj, 'balance_r')
                        ui.label('R').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-green') \
                            .bind_value(class_obj, 'balance_g')
                        ui.label('G').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-blue') \
                            .bind_value(class_obj, 'balance_b')
                        ui.label('B').classes('self-center')
                ui.button('reset', on_click=lambda: reset_rgb(class_obj)).classes('self-center')

    with ui.card().classes('text-sm shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]'):
        with ui.row().classes('w-20').style('justify-content: flex-end'):
            ui.label('saturation')
            saturation_slider = ui.slider(min=0, max=100, step=1, value=0).props('label-always')
            saturation_slider.on('wheel', create_wheel_handler(saturation_slider))
            saturation_slider.bind_value(class_obj, 'saturation')

            ui.label('brightness').classes('text-right')
            brightness_slider = ui.slider(min=0, max=100, step=1, value=0).props('label-always')
            brightness_slider.on('wheel', create_wheel_handler(brightness_slider))
            brightness_slider.bind_value(class_obj, 'brightness')

            ui.label('contrast')
            contrast_slider = ui.slider(min=0, max=100, step=1, value=0).props('label-always')
            contrast_slider.on('wheel', create_wheel_handler(contrast_slider))
            contrast_slider.bind_value(class_obj, 'contrast')

            ui.label('sharpen')
            sharpen_slider = ui.slider(min=0, max=100, step=1, value=0).props('label-always')
            sharpen_slider.on('wheel', create_wheel_handler(sharpen_slider))
            sharpen_slider.bind_value(class_obj, 'sharpen')

            ui.checkbox('auto') \
                .bind_value(class_obj, 'auto_bright', forward=lambda value: value) \
                .tooltip('Auto bri/contrast')
            clip_hist_percent_slider = ui.slider(min=0, max=100, step=1).props('label-always')
            clip_hist_percent_slider.on('wheel', create_wheel_handler(clip_hist_percent_slider))
            clip_hist_percent_slider.bind_value(class_obj, 'clip_hist_percent')


async def create_cpu_chart(CastAPI):
    """Creates and displays a CPU usage chart.

    This function generates an interactive chart that displays CPU usage
    over time.

    Args:
        CastAPI: The CastAPI instance.
    """

    CastAPI.cpu_chart = ui.echart({
        'darkMode': 'auto',
        'legend': {
            'show': 'true',
            'data': []
        },
        'textStyle': {
            'fontSize': 1,
            'color': '#d2a'
        },
        'grid': {
            'top': 60
        },
        'tooltip': {
            'trigger': 'axis'
        },
        'xAxis': {
            'type': 'category',
            'data': []
        },
        'yAxis': {
            'type': 'value'
        },
        'series': [{
            'data': [],
            'name': 'CPU %',
            'areaStyle': {'color': '#535894', 'opacity': 0.5},
            'type': 'line'
        }]
    }).style('height:80px ')


async def player_media_info(player_media):
    """Displays media information and thumbnail.

    This function retrieves and displays media information in a dialog,
    including a thumbnail extracted from the image/video.

    Args:
        player_media (str): The path or URL of the media file.
    """

    with ui.dialog() as dialog:
        dialog.open()
        data = await CV2Utils.get_media_info(player_media)
        await ui.json_editor({'content': {'json': data }}) \
                .run_editor_method('updateProps', {'readOnly': True, 'mode': 'tree'})

        with ui.card():
            ui.label(player_media)
            extractor = VideoThumbnailExtractor(player_media)
            await extractor.extract_thumbnails(times_in_seconds=[5])  # Extract thumbnail at 5 seconds
            thumbnails_frame = extractor.get_thumbnails()
            img = Image.fromarray(thumbnails_frame[0])
            ui.image(img).classes('w-32')


async def player_url_info(player_url):
    """ Grab YouTube information from an Url """

    async def yt_search():
        data = await Utils.list_yt_formats(player_url)
        with ui.dialog() as dialog:
            dialog.open()
            editor = ui.json_editor({'content': {'json': data}}) \
                .run_editor_method('updateProps', {'readOnly': True, 'mode': 'tree'})

    ui.notify('Grab info from Url ...')
    ui.timer(.1, yt_search, once=True)


async def display_formats():
    """Displays available AV formats.

    This function retrieves and displays a list of available audio and video
    formats in a dialog.
    """

    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.list_av_formats()}}) \
            .run_editor_method('updateProps', {'readOnly': True})


async def display_codecs():
    """Displays available AV codecs.

    This function retrieves and displays a list of available audio and video
    codecs in a dialog.
    """

    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.list_av_codecs()}}) \
            .run_editor_method('updateProps', {'readOnly': True})


def reset_rgb(class_name):
    """ reset RGB value """

    class_name.balance_r = 0
    class_name.balance_g = 0
    class_name.balance_b = 0


async def cast_device_manage(class_name, Netdevice):
    with ui.dialog() as dialog, ui.card().classes('w-1/2'):
        dialog.open()
        columns = [
            {'field': 'number', 'editable': True, 'sortable': True, 'checkboxSelection': True},
            {'field': 'ip', 'editable': True},
            {'field': 'id', 'hide': True},
        ]
        rows = [
        ]

        def handle_cell_value_change(e):
            new_row = e.args['data']
            ui.notify(f'Updated row to: {e.args["data"]}')
            rows[:] = [row | new_row if row['id'] == new_row['id'] else row for row in rows]

        aggrid = ui.aggrid({
            'columnDefs': columns,
            'rowData': rows,
            'rowSelection': 'multiple',
            'stopEditingWhenCellsLoseFocus': True,
        }).on('cellValueChanged', handle_cell_value_change)

        def add_row():
            row_new_id = max((dx['id'] for dx in rows), default=-1) + 1
            rows.append({'number': 0, 'ip': '127.0.0.1', 'id': row_new_id})
            aggrid.update()

        def add_net():
            i = len(class_name.cast_devices)
            for net in Netdevice.http_devices:
                i += 1
                row_new_id = max((dx['id'] for dx in rows), default=-1) + 1
                rows.append({'number': i, 'ip': Netdevice.http_devices[net]['address'], 'id': row_new_id})
                aggrid.update()

        async def update_cast_devices():
            new_cast_devices = []
            for row in await aggrid.get_selected_rows():
                new_cast_device = tuple((row["number"], row["ip"]))
                new_cast_devices.append(new_cast_device)
            sorted_devices = sorted(new_cast_devices, key=lambda x: x[0])
            class_name.cast_devices.clear()
            class_name.cast_devices.extend(sorted_devices)
            dialog.close()
            ui.notify('New data entered into cast_devices, click on validate/refresh to see them ')

        for item in class_name.cast_devices:
            new_id = max((dx['id'] for dx in rows), default=-1) + 1
            rows.append({'number': item[0], 'ip': item[1], 'id': new_id})

        with ui.row():
            ui.button('Add row', on_click=add_row)
            ui.button('Add Net', on_click=add_net)
            ui.button('Select all', on_click=lambda: aggrid.run_grid_method('selectAll'))
            ui.button('Validate', on_click=lambda: update_cast_devices())
            ui.button('Close', color='red', on_click=lambda: dialog.close())


async def generate_carousel(class_obj):
    """ Images carousel for Desktop and Media """

    for i in range(len(class_obj.frame_buffer)):
        with ui.carousel_slide().classes('-p0'):
            carousel_image = Image.fromarray(class_obj.frame_buffer[i])
            h, w = class_obj.frame_buffer[i].shape[:2]
            img = ui.interactive_image(carousel_image.resize(size=(640, 360))).classes('w-[640]')
            with img:
                ui.button(
                    text=f'{str(i)}:size:{str(w)}x{str(h)}', icon='tag'
                ).props('flat fab color=white').classes(
                    'absolute top-0 left-0 m-2'
                ).tooltip(
                    'Image Number'
                )


async def multi_preview(class_name):
    """
    Generate matrix image preview for multicast
    :return:
    """
    dialog = ui.dialog().style('width: 200px')
    with dialog:
        grid_col = ''.join('1fr ' for _ in range(class_name.cast_x))
        with ui.grid(columns=grid_col).classes('w-full gap-0'):
            for i in range(len(class_name.cast_frame_buffer)):
                with ui.image(Image.fromarray(class_name.cast_frame_buffer[i])).classes('w-60'):
                    ui.label(str(i))
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('FULL', icon='preview', on_click=dialog.open).tooltip('View ALL images')


async def cast_devices_view(class_name):
    """
    view cast_devices list
    :return:
    """
    dialog = ui.dialog().style('width: 800px')
    with dialog:
        with ui.card():
            with ui.grid(columns=3):
                for i in range(len(class_name.cast_devices)):
                    with ui.card():
                        ui.label(f'No: {str(class_name.cast_devices[i][0])}')
                        if Utils.validate_ip_address(str(class_name.cast_devices[i][1])):
                            text_decoration = "color: green; text-decoration: underline"
                        else:
                            text_decoration = "color: red; text-decoration: red wavy underline"

                        ui.link(
                            f'IP  :  {str(class_name.cast_devices[i][1])}',
                            f'http://{str(class_name.cast_devices[i][1])}',
                            new_tab=True,
                        ).style(text_decoration)
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('DEVICE', icon='preview', on_click=dialog.open).tooltip('View Cast devices')


async def player_pick_file(CastAPI) -> None:
    """ Select file to read for video CastAPI.player """

    result = await LocalFilePicker(cfg_mgr.app_root_path('media'), multiple=False)
    ui.notify(f'Selected :  {result}')

    if result is not None:
        try:
            result = str(result[0])

            CastAPI.player.set_source(result)
            CastAPI.player.update()
        except Exception as e:
            ui.notify(f'Error :  {e}')


async def generate_actions_to_cast(class_name, class_threads, action_to_casts, info_data):
    """ Generate expansion for each cast with icon/action """

    casts_row = ui.row()
    with casts_row:
        for item_th in class_threads:
            item_exp = ui.expansion(item_th, icon='cast') \
                .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] w-96')
            with item_exp:
                with ui.row().classes('m-auto'):
                    ui.button(icon='delete_forever',
                              on_click=lambda item_v=item_th, item_exp_v=item_exp: action_to_casts(
                                  class_name=class_name,
                                  cast_name=item_v,
                                  action='stop',
                                  params='',
                                  clear=False,
                                  execute=True,
                                  data=info_data,
                                  exp_item=item_exp_v)
                              ).classes('shadow-lg').tooltip('Cancel Cast')
                    ui.button(icon='add_photo_alternate',
                              on_click=lambda item_v=item_th: action_to_casts(class_name=class_name,
                                                                              cast_name=item_v,
                                                                              action='shot',
                                                                              params='',
                                                                              clear=False,
                                                                              execute=True)
                              ).classes('shadow-lg').tooltip('Capture picture')
                    ui.button(icon='cancel_presentation',
                              on_click=lambda item_v=item_th: action_to_casts(class_name=class_name,
                                                                              cast_name=item_v,
                                                                              action='close-preview',
                                                                              params='',
                                                                              clear=False,
                                                                              execute=True)
                              ).classes('shadow-lg').tooltip('Stop Preview')
                    ui.button(icon='preview',
                              on_click=lambda item_v=item_th: action_to_casts(class_name=class_name,
                                                                              cast_name=item_v,
                                                                              action='open-preview',
                                                                              params='',
                                                                              clear=False,
                                                                              execute=True)
                              ).classes('shadow-lg').tooltip('Open Preview Window')
                    ui.button(icon='settings_ethernet',
                              on_click=lambda item_v=item_th: action_to_casts(class_name=class_name,
                                                                              cast_name=item_v,
                                                                              action='host',
                                                                              params='',
                                                                              clear=False,
                                                                              execute=True,
                                                                              data=info_data)
                              ).classes('shadow-lg').tooltip('Change IP devices')
                    ui.button(icon='grid_view',
                              on_click=lambda item_v=item_th: action_to_casts(class_name=class_name,
                                                                              cast_name=item_v,
                                                                              action='multicast',
                                                                              params='',
                                                                              clear=False,
                                                                              execute=True)
                              ).classes('shadow-lg').tooltip('Multicast Effects')

                base64 = 'data:image/png;base64,' + info_data[item_th]["data"]['img']
                ui.image(base64).classes('w-84 m-auto animate__animated animate__fadeInDown').tailwind.border_width('8')
                def show_details(item_v):
                    with ui.dialog() as dialog:
                        dialog.open()
                        editor = ui.json_editor({'content': {'json': info_data[item_v]["data"]}}) \
                         .run_editor_method('updateProps', {'readOnly': True})
                ui.button('Details', on_click=lambda item_v=item_th: show_details(item_v))


async def edit_ip(class_obj):
    """Creates and displays UI elements for editing the IP address.

    This function generates a checkbox for enabling/disabling WLED and an
    input field for the IP address. It also sets up an API request to
    update the attribute when the input field loses focus.

    Args:
        class_obj: The class instance to bind the IP address to.
    """
    new_wled = ui.checkbox('wled')
    new_wled.bind_value(class_obj, 'wled')
    new_wled.tooltip('Is That a WLED Device ?')
    with ui.row():
        new_host = ui.input('IP', value=class_obj.host)
        new_host.tooltip('IP address of the device')
        class_name = 'unknown'
        if 'Media' in str(class_obj):
            class_name = 'Media'
        elif 'Desktop' in str(class_obj):
            class_name = 'Desktop'
        endpoint = f'/api/{class_name}/update_attribute'
        new_host.on('blur', lambda: Utils.api_request(method='PUT',
                                                          endpoint=endpoint,
                                                          params={"param":"host","value":new_host.value}))
        net_icon = ui.icon('view_list', size='xs')
        net_icon.style(add='cursor: pointer')
        net_icon.on('click', lambda: net_view_button())



async def edit_rate_x_y(class_obj):
    """Creates and displays UI elements for editing rate, scale width, and scale height.

    This function generates number input fields for adjusting the frame rate,
    scaling width, and scaling height.

    Args:
        class_obj: The class instance to bind the values to.
    """

    new_rate = ui.number('FPS', value=class_obj.rate, min=1, max=60, precision=0)
    new_rate.tooltip('Desired Frame Per Second, max = 60')
    new_rate.bind_value(class_obj, 'rate', forward=lambda value: int(value or 1))
    new_scale_width = ui.number('Scale Width', value=class_obj.scale_width, min=8, max=1920, precision=0)
    new_scale_width.tooltip('Cast Width')
    new_scale_width.bind_value(class_obj, 'scale_width', forward=lambda value: int(value or 8))
    new_scale_height = (ui.number('Scale Height', value=class_obj.scale_height, min=8, max=1080, precision=0))
    new_scale_height.tooltip('Cast Height')
    new_scale_height.bind_value(class_obj, 'scale_height', forward=lambda value: int(value or 8))

async def edit_multicast(class_obj):
    """Creates and displays multicast settings controls.

    This function generates UI elements for configuring multicast settings,
    including enabling/disabling multicast and setting the matrix dimensions.

    Args:
        class_obj: The class instance to bind the multicast settings to.
    """

    new_multicast = ui.checkbox('Multicast')
    new_multicast.tooltip('Select if you want Multicast feature')
    new_multicast.bind_value(class_obj, 'multicast')
    new_cast_x = ui.number('Matrix X', value=class_obj.cast_x, min=1, max=1920, precision=0)
    new_cast_x.tooltip('Increase Matrix * X')
    new_cast_x.bind_value(class_obj, 'cast_x', forward=lambda value: int(value or 1))
    new_cast_y = ui.number('Matrix Y', value=class_obj.cast_y, min=1, max=1080, precision=0)
    new_cast_y.tooltip('Increase Matrix * Y')
    new_cast_y.bind_value(class_obj, 'cast_y', forward=lambda value: int(value or 1))


async def edit_capture(class_obj):
    """Creates and displays frame capture settings controls.

    This function generates UI elements for configuring frame capture
    settings, including enabling/disabling capture and setting the maximum
    number of frames to capture.  For `CASTMedia` instances, it also
    provides a control for seeking to a specific frame.

    Args:
        class_obj: The class instance to bind the capture settings to.
    """

    new_put_to_buffer = ui.checkbox('Capture Frame')
    new_put_to_buffer.tooltip('Select if you want to capture images')
    new_put_to_buffer.bind_value(class_obj, 'put_to_buffer')
    new_frame_max = ui.number('Number to Capture', value=class_obj.frame_max, min=1, max=30, precision=0)
    new_frame_max.tooltip('Max number of frame to capture')
    new_frame_max.bind_value(class_obj, 'frame_max', forward=lambda value: int(value or 0))
    class_name = class_obj.__class__.__name__
    if class_name == 'CASTMedia':
        new_frame_index = ui.number('Seek to frame N°', value=class_obj.frame_index, min=0, precision=0)
        new_frame_index.tooltip('Position media to frame number')
        new_frame_index.bind_value(class_obj, 'frame_index', forward=lambda value: int(value or 0))


async def edit_protocol(class_obj):
    """Creates and displays a protocol selection dropdown.

    This function generates a dropdown menu for selecting the
    communication protocol.

    Args:
        class_obj: The class instance to bind the protocol selection to.
    """

    new_protocol = ui.select(['ddp', 'artnet', 'e131', 'other'], label='Protocol')
    new_protocol.bind_value(class_obj, 'protocol')
    new_protocol.classes('w-40')
    new_protocol.tooltip('Select other to test experimental feature ....')


async def edit_artnet(class_obj):
    """Creates and displays Art-Net / e131 settings controls.

    This function generates UI elements for configuring Art-Net / e131 settings,
    including name, universe, pixel count, priority, universe size, offset, and channels per pixel.

    Args:
        class_obj: The class instance to bind the Art-Net settings to.
    """

    new_artnet_name = ui.input('E131 name', value=str(class_obj.e131_name))
    new_artnet_name.bind_value(class_obj, 'e131_name')
    new_artnet_name.classes('w-40')
    new_artnet_name.tooltip('name for e131')
    new_universe = ui.number('Universe', placeholder='start', min=0, max=63999, step=1, value=1)
    new_universe.bind_value(class_obj, 'universe')
    new_universe.classes('w-40')
    new_universe.tooltip('universe start number e131/artnet')
    new_pixel = ui.number('Pixels', placeholder='total number', min=1, max=63999, step=1, value=0)
    new_pixel.bind_value(class_obj, 'pixel_count')
    new_pixel.classes('w-40')
    new_pixel.tooltip('number of pixels e131/artnet')
    new_priority = ui.number('Priority', placeholder='packet priority', min=0, max=200, step=1, value=0)
    new_priority.bind_value(class_obj, 'packet_priority')
    new_priority.classes('w-40')
    new_priority.tooltip('priority for e131')
    new_universe_size = ui.number('Size', placeholder='Universe size', min=1, max=512, step=1, value=510)
    new_universe_size.bind_value(class_obj, 'universe_size')
    new_universe_size.classes('w-40')
    new_universe_size.tooltip('size of each universe 510 for e131/ 512 for artnet')
    """
    new_offset = ui.number('Offset', placeholder='channel', min=0, max=1024, step=1, value=0)
    new_offset.bind_value(class_obj, 'channel_offset')
    new_offset.classes('w-40')
    new_offset.tooltip('The channel offset within the universe. e131/artnet')
    
    new_channels_per_pixel = ui.number('Channels', placeholder='rgb', min=1, max=4, step=1, value=3)
    new_channels_per_pixel.bind_value(class_obj, 'channels_per_pixel')
    new_channels_per_pixel.classes('w-40')
    new_channels_per_pixel.tooltip('Channels to use for e131/artnet, RGB = 3 RGBW = 4.')
    """

async def apply_custom():
    """
    Layout Colors come from config file
    bg image can be customized
    :return:
    """
    ui.colors(primary=cfg_mgr.color_config['primary'],
              secondary=cfg_mgr.color_config['secondary'],
              accent=cfg_mgr.color_config['accent'],
              dark=cfg_mgr.color_config['dark'],
              positive=cfg_mgr.color_config['positive'],
              negative=cfg_mgr.color_config['negative'],
              info=cfg_mgr.color_config['info'],
              warning=cfg_mgr.color_config['warning']
              )

    # custom font (experimental)
    font_file = cfg_mgr.app_config['font_file']
    if font_file != '':
        font_weight = 100
        font_style = 'normal'
        size_adjust = '90%'
        if cfg_mgr.app_config['font_weight'] is not None:
            font_weight = cfg_mgr.app_config['font_weight']
        if cfg_mgr.app_config['font_style'] is not None:
            font_style = cfg_mgr.app_config['font_style']
        if cfg_mgr.app_config['size_adjust'] is not None:
            size_adjust = cfg_mgr.app_config['size_adjust']

        FontSetApplication(font_path=font_file,font_style=font_style,font_weight=font_weight, size_adjust=size_adjust)

    # custom bg
    ui.query('body').style(f'background-image: url({cfg_mgr.custom_config["bg_image"]}); '
                           'background-size: cover;'
                           'background-repeat: no-repeat;'
                           'background-position: center;')

def custom_openapi():
    """got ws page into FastAPI docs"""

    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="WLEDVideoSync",
        version="1.0.0",
        description="API docs",
        routes=app.routes,
    )
    # Add WebSocket route to the schema
    openapi_schema["paths"]["/ws/docs"] = {
        "get": {
            "summary": "webSocket - only for reference",
            "description": "websocket_info",
            "responses": {200: {}},
            "tags": ["websocket"]
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


async def run_gif_player(wled_host):
    """Runs the GIF player on a WLED device.

    This function checks if the 'gifplayer.htm' file exists on the WLED device.
    If it does not exist, it uploads the file and then navigates to the GIF player page in a new browser tab.

    Args:
        wled_host: The IP address or hostname of the WLED device.
    """
    player_exist = await Utils.check_wled_file_exists(wled_host, 'gifplayer.htm')
    if not player_exist:
        await run.io_bound(
            lambda: Utils.wled_upload_file(wled_host, cfg_mgr.app_root_path('xtra/gif/gifplayer.htm')))
    ui.navigate.to(f'http://{wled_host}/gifplayer.htm', new_tab=True)


async def media_dev_view_page():
    """
    Display media devices into the Json Editor
    :return:
    """
    def fetch_dev():
        with ui.dialog() as dialog, ui.card():
            dialog.open()
            editor = ui.json_editor({'content': {'json': Utils.dev_list}}) \
                .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog.close, color='red')

    ui.button('Media devices', on_click=fetch_dev, color='bg-red-800').tooltip('View Media devices')

"""
local file picker class
"""

class LocalFilePicker(ui.dialog):
    """Local File Picker

    This is  simple file picker that allows you to select a file from the local filesystem where NiceGUI is running.
    Right-click on a file will display image/video if available.

    :param directory: The directory to start in.
    :param upper_limit: The directory to stop at (None: no limit, default: same as the starting directory).
    :param multiple: Whether to allow multiple files to be selected.
    :param show_hidden_files: Whether to show hidden files.
    :param thumbs : generate thumbnails
    """

    def __init__(self, directory: str, *,
                 upper_limit: Optional[str] = ...,
                 multiple: bool = False, show_hidden_files: bool = False, thumbs: bool = True,
                 dir_filter: Optional[str] = None) -> None:

        super().__init__()

        self.drives_toggle = None
        directory = cfg_mgr.app_root_path(directory)
        self.path = Path(directory).expanduser()
        if upper_limit is None:
            self.upper_limit = None
        else:
            self.upper_limit = Path(directory if upper_limit == ... else upper_limit).expanduser()
        self.show_hidden_files = show_hidden_files
        self.filter = dir_filter
        # for the right click (thumb)
        self.supported_thumb_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.avi', '.mkv', '.mp4', '.mov')

        with (self, ui.card()):
            self.add_drives_toggle()
            self.grid = ui.aggrid({
                'columnDefs': [{'field': 'name', 'headerName': 'File'}],
                'rowSelection': 'multiple' if multiple else 'single',
            }, html_columns=[0]).classes('w-96').on('cellDoubleClicked', self.handle_double_click)

            # inform on right click
            self.grid.on('cellClicked', self.click)

            # open image or video thumb
            self.grid.on('cellContextMenu', self.right_click)

            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=self.close).props('outline')
                ui.button('Ok', on_click=self._handle_ok)

        self.update_grid()

        self.thumbs = thumbs

    def add_drives_toggle(self):
        """Adds a drive selection toggle for Windows platforms.

        This method creates a toggle UI element listing available drives if running on Windows.
        """
        if PLATFORM == 'win32':
            import win32api
            drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
            self.drives_toggle = ui.toggle(drives, value=drives[0], on_change=self.update_drive)

    def update_drive(self):
        """Updates the current directory based on the selected drive.

        This method sets the file picker's path to the selected drive and refreshes the file grid.
        """
        self.path = Path(self.drives_toggle.value).expanduser()
        self.update_grid()

    def update_grid(self) -> None:
        """Updates the file grid with the contents of the current directory.

        This method refreshes the grid to display files and directories in the current path,
        applying filters and sorting as needed, and optionally includes a parent directory entry.
        """
        if self.filter:
            paths = list(self.path.glob(f'*{self.filter}'))
        else:
            paths = list(self.path.glob('*'))
        if not self.show_hidden_files:
            paths = [p for p in paths if not p.name.startswith('.')]
        paths.sort(key=lambda p: p.name.lower())
        paths.sort(key=lambda p: not p.is_dir())

        self.grid.options['rowData'] = [
            {
                'name': f'📁 <strong>{p.name}</strong>' if p.is_dir() else p.name,
                'path': str(p),
            }
            for p in paths
        ]
        if self.upper_limit is None and self.path != self.path.parent or \
                self.upper_limit is not None and self.path != self.upper_limit:
            self.grid.options['rowData'].insert(0, {
                'name': '📁 <strong>..</strong>',
                'path': str(self.path.parent),
            })
        self.grid.update()

    def handle_double_click(self, e: events.GenericEventArguments) -> None:
        """Handles double-click events on the file grid to open directories or select files.

        If a directory is double-clicked, the grid updates to show its contents.
        If a file is double-clicked, its path is submitted for selection.

        Args:
            e: The event arguments containing information about the double-clicked cell.
        """
        self.path = Path(e.args['data']['path'])
        if self.path.is_dir():
            self.update_grid()
        else:
            self.submit([str(self.path)])

    async def _handle_ok(self):
        """Handles the OK button click event to submit selected file paths.

        This method retrieves the selected rows from the file grid and submits their paths.
        """
        rows = await self.grid.get_selected_rows()
        self.submit([r['path'] for r in rows])

    def click(self, e: events.GenericEventArguments) -> None:
        """Handles click events on file grid cells to prompt for preview.

        If the clicked file is a supported image or video, a notification is shown
        suggesting the user to right-click for a preview.

        Args:
            e: The event arguments containing information about the clicked cell.
        """
        self.path = Path(e.args['data']['path'])
        if self.path.suffix.lower() in self.supported_thumb_extensions and self.path.is_file() and self.thumbs:
            ui.notify('Right-click for Preview', position='top')

    def media_erase(self, media_name: str, dialog: ui.dialog):
        """Deletes the specified media file from the filesystem.

        Args:
            media_name (str): The full path of the file to delete.
            dialog (ui.dialog): The dialog to close after deletion.
        """
        try:
            file_to_delete = Path(media_name)
            if file_to_delete.is_file():
                file_to_delete.unlink()
                nice_logger.info(f"Successfully deleted: {file_to_delete.name}")
                ui.notify(f"Successfully deleted: {file_to_delete.name}", type='positive')
                dialog.close()
                self.update_grid()  # Refresh the file list
            else:
                nice_logger.warning(f"File not found, could not delete: {file_to_delete.name}")
                ui.notify(f"File not found: {file_to_delete.name}", type='warning')
        except Exception as e:
            nice_logger.error(f"Error deleting file {media_name}: {e}")
            ui.notify(f"Error deleting file: {e}", type='negative')

    async def right_click(self, e: events.GenericEventArguments) -> None:
        """Handles right-click events to preview image or video thumbnails.

        When a supported file is right-clicked, this method opens a dialog displaying
        a thumbnail preview of the image or video at a specific timestamp.

        Args:
            e: The event arguments containing information about the clicked cell.
        """
        self.path = Path(e.args['data']['path'])
        if self.path.suffix.lower() in self.supported_thumb_extensions and self.path.is_file() and self.thumbs:
            with ui.dialog() as thumb:
                thumb.open()
                with ui.card().classes('w-full'):
                    row = await self.grid.get_selected_row()
                    if row is not None:
                        extractor = VideoThumbnailExtractor(row['path'])
                        await extractor.extract_thumbnails(times_in_seconds=[5])  # Extract thumbnail at 5 seconds
                        thumbnails_frame = extractor.get_thumbnails()
                        img = Image.fromarray(thumbnails_frame[0])
                        ui.image(img)
                        ui.label(row['path'])
                        with ui.row().classes('self-center'):
                            ui.button('Close', on_click=thumb.close)
                            with ui.list().props('bordered'):
                                with ui.slide_item() as slide_item:
                                    with ui.item():
                                        with ui.item_section().props('avatar'):
                                            ui.icon('delete', color='red')
                                    with slide_item.right():
                                        ui.button('Erase', on_click=lambda:self.media_erase(row['path'], thumb))
                    else:
                        ui.notify('Made a selection before ....', position='center', color='gray')


"""
Animate css class
"""

class AnimatedElement:
    """
    Add animation to UI Element, in / out
        In for create element
        Out for delete element
    Following is necessary as it's based on Animate.css
    # Add Animate.css to the HTML head
    ui.add_head_html(""
    <link rel="stylesheet" href="assets/css/animate.min.css"/>
    "")
    app.add_static_files('/assets', 'assets')
    Param:
        element_type : nicegui element e.g. card, label, ...
        animation_name : see https://animate.style/
        duration : custom animation delay
    """

    def __init__(self, element_type:type[any], animation_name_in='fadeIn', animation_name_out='fadeOut', duration=1.5):
        self.element_type = element_type
        self.animation_name_in = animation_name_in
        self.animation_name_out = animation_name_out
        self.duration = duration

    def generate_animation_classes(self, animation_name):
        """Generates animation and duration CSS classes for Animate.css.

        This method returns the appropriate animation and duration class names
        based on the provided animation name and the configured duration.

        Args:
            animation_name: The name of the animation to use.

        Returns:
            A tuple containing the animation class and the duration class.
        """
        # Generate the animation and duration classes
        animation_class = f'animate__{animation_name}'
        duration_class = f'custom-duration-{self.duration}s'
        return animation_class, duration_class

    def add_custom_css(self):
        """Adds custom CSS for animation duration to the UI.

        This method injects a style block into the HTML head to set the animation duration
        for elements using the custom duration class.
        """
        # Add custom CSS for animation duration
        custom_css = f"""
        <style>
        .custom-duration-{self.duration}s {{
          animation-duration: {self.duration}s;
        }}
        </style>
        """
        ui.add_head_html(custom_css)

    def create_element(self, *args, **kwargs):
        """ Add class for in """
        self.add_custom_css()
        animation_class, duration_class = self.generate_animation_classes(self.animation_name_in)
        element = self.element_type(*args, **kwargs)
        element.classes(f'animate__animated {animation_class} {duration_class}')
        return element

    def delete_element(self, element):
        """ Add class for out and delete """
        animation_class, duration_class = self.generate_animation_classes(self.animation_name_out)
        element.classes(f'animate__animated {animation_class} {duration_class}')
        # Delay the actual deletion to allow the animation to complete
        ui.timer(self.duration, lambda: element.delete(), once=True)


"""
Youtube search class
"""

class YtSearch:
    """
    Search YT Video from input
    Display thumb and YT Plyer
    On click, copy YT Url to clipboard
    """

    def __init__(self, input_url, anime: bool = False):
        self.yt_search = None
        self.yt_anime = anime
        self.videos_search = None
        self.yt_url_copied = None
        self.input_url = input_url

        ui.separator()
        with ui.row():
            self.my_search = ui.input('YT search')
            self.search_button = ui.button('search', icon='restore_page', color='blue') \
                .tooltip('Click to Validate')
            self.search_button.on_click(lambda: self.search_youtube())
            self.next_button = ui.button('More', on_click=lambda: self.next_search())
            self.next_button.set_visibility(False)
            self.number_found = ui.label('Result : ')

        self.search_result = ui.card()
        with self.search_result:
            ui.label('Search could take some time ....').classes('animate-pulse')

        self.yt_player = ui.page_sticky()

    def youtube_player(self, yt_id):
        """ YT Player in iframe """

        self.yt_player.clear()
        with self.yt_player:
            player = ui.card()
            if self.yt_anime:
                player.classes(add='animate__animated animate__slideInRight')
            youtube_url = f"https://www.youtube.com/embed/{yt_id}"
            with player:
                ui.html('<iframe width="350" height="230" '
                        f'src="{youtube_url}" '
                        'title="YouTube video player" '
                        'frameborder="0" '
                        'allow="autoplay;clipboard-write;encrypted-media;picture-in-picture" '
                        'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen>'
                        '</iframe>')

    async def search_youtube(self):
        """ Run Search YT from input """

        async def run_search():
            await create_task(self.py_search(self.my_search.value))

        self.search_button.props('loading')
        self.search_result.clear()
        ui.timer(.5, run_search, once=True)

    async def py_search(self, data):
        """ Search for YT from input """

        self.videos_search = Search(data)
        self.yt_search = self.videos_search.videos

        # number found
        number = len(self.yt_search)
        self.number_found.text = f'Number found: {number}'
        # activate 'more' button
        if number > 0:
            await run.io_bound(self.search_first_iterate)
            self.next_button.set_visibility(True)
            # re-create  result page
            await self.create_yt_page()
        else:
            self.number_found.text = 'Nothing Found'

        self.search_button.props(remove='loading')

    async def next_search(self):
        """ Next if you want more """

        self.search_button.props('loading')
        await run.io_bound(self.videos_search.get_next_results)
        self.yt_search = self.videos_search.videos
        self.number_found.text = f'Number found: {len(self.yt_search)}'
        await run.io_bound(self.search_first_iterate)
        await self.create_yt_page()
        self.search_button.props(remove='loading')

    def search_first_iterate(self):
        """Iterates through the YouTube search results and prints each video title.

        This method loops over the current YouTube search results and prints the title of each video to the console.
        It is primarily used for debugging or logging purposes.
        Since release 8.13.1 of Pytubefix, access search result at first time is very long...this avoids connect timeout
        """
        for i in range(len(self.yt_search)):
            a=self.yt_search[i].title
            nice_logger.info(f'We prepare data for : {a}')

    def url_copied(self, url):
        """Copies the provided YouTube URL to the clipboard and updates the input field.

        This method writes the given URL to the clipboard, updates the internal state,
        sets the input field value, and displays a notification to the user.

        Args:
            url: The YouTube URL to copy and set.
        """
        ui.clipboard.write(url),
        self.yt_url_copied = url
        self.input_url.value = url
        ui.notify('YT Url copied')

    async def create_yt_page(self):
        """ Create YT search result """

        # clear as we recreate
        self.search_result.clear()
        # create
        with self.search_result.classes('w-full self-center'):
            for i in range(len(self.yt_search)):
                ui.separator()
                ui.label(self.yt_search[i].title)
                with ui.row(wrap=False).classes('w-1/2'):
                    yt_image = ui.image(self.yt_search[i].thumbnail_url).style(add='width: 150px;')
                    yt_image.on('mouseenter', lambda yt_str=self.yt_search[i]: self.youtube_player(yt_str.video_id))
                    with ui.column():
                        ui.label(f'Length: {self.yt_search[i].length}')
                        yt_url = ui.label(self.yt_search[i].watch_url)
                        yt_url.tooltip('Click to copy')
                        yt_url.style('text-decoration: underline; cursor: pointer;')
                        yt_url.on('click', lambda my_yt=yt_url: self.url_copied(my_yt.text))
                        with ui.row():
                            yt_watch_close = ui.icon('videocam_off', size='sm')
                            yt_watch_close.tooltip('Player OFF')
                            yt_watch_close.style('cursor: pointer')
                            yt_watch_close.on('click', lambda: self.yt_player.clear())
                            yt_watch = ui.icon('smart_display', size='sm')
                            yt_watch.tooltip('Player On')
                            yt_watch.style('cursor: pointer')
                            yt_watch.on('click', lambda yt_str=self.yt_search[i]: self.youtube_player(yt_str.video_id))


"""
ui log element class
"""

class LogElementHandler(logging.Handler):
    """ A logging handler that emits messages to a log element."""

    def __init__(self, element: ui.log, level: int = logging.NOTSET) -> None:
        """Initializes the LogElementHandler with a UI log element and log level.

        This constructor sets up the handler to emit log messages to the provided UI log element,
        and configures the log message format.

        Args:
            element: The NiceGUI log element to which log messages will be pushed.
            level: The logging level for the handler.
        """
        self.element = element
        super().__init__(level)
        # define format for the LogRecord
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # set format
        self.setFormatter(formatter)


    def emit(self, record: logging.LogRecord) -> None:
        """Emits a log record to the associated UI log element.

        This method formats the log record and pushes it to the UI log element for display.
        If an error occurs during emission, it is handled by the logging framework.

        Args:
            record: The log record to be emitted.
        """
        try:
            msg = self.format(record)
            self.element.push(msg)
        except Exception:
            self.handleError(record)
