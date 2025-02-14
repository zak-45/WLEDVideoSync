"""
# a: zak-45
# d: 25/08/2024
# v: 1.0.0
#
# niceutils
#
#          NiceGUI utilities
#
# used by CastAPI mainly
#
"""
import sys
import psutil

from nicegui import ui, events
from datetime import datetime
from str2bool import str2bool
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils
from src.utl.cv2utils import VideoThumbnailExtractor
from PIL import Image
from pathlib import Path
from typing import Optional
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger.utils')


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

    if str2bool(cfg_mgr.custom_config['cpu-chart']) and CastAPI.cpu_chart is not None:
        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")
    
        CastAPI.cpu_chart.options['series'][0]['data'].append(CastAPI.cpu)
        CastAPI.cpu_chart.options['xAxis']['data'].append(date_time_str)
    
        CastAPI.cpu_chart.update()

    if CastAPI.cpu >= 65:
        ui.notify('High CPU utilization', type='negative', close_button=True)
    if CastAPI.ram >= 95:
        ui.notify('High Memory utilization', type='negative', close_button=True)


def animate_wled_image(CastAPI, visible):
    """ toggle main image animation """

    if visible:
        CastAPI.w_image.classes(add='animate__flipOutX', remove='animate__flipInX')
        ui.timer(0.7, lambda: CastAPI.w_image.set_visibility(False), once=True)
    else:
        CastAPI.w_image.classes(add='animate__flipInX', remove='animate__flipOutX')
        CastAPI.w_image.set_visibility(True)


async def head_set(name, target, icon):
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
            ui.button('Main', on_click=lambda: ui.navigate.to('/'), icon='home')
        if name != 'Manage':
            ui.button('Manage', on_click=lambda: ui.navigate.to('/Manage'), icon='video_settings')
        if name != 'Desktop Params':
            ui.button('Desktop Params', on_click=lambda: ui.navigate.to('/Desktop'), icon='computer')
        if name != 'Media Params':
            ui.button('Media Params', on_click=lambda: ui.navigate.to('/Media'), icon='image')
        if str2bool(cfg_mgr.app_config['fastapi_docs']):
            ui.button('API', on_click=lambda: ui.navigate.to('/docs', new_tab=True), icon='api')
        ui.icon('info', size='sm').on('click', lambda: app_info()).style('cursor:pointer')


def app_info():
    """ display app , compile version """

    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.compile_info()}}) \
            .run_editor_method('updateProps', {'readOnly': True})


def sync_button(CastAPI, Media):
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


def cast_manage(CastAPI, Desktop, Media):
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
        editor = ui.json_editor({'content': {'json': CV2Utils.get_media_info(player_media)}}) \
            .run_editor_method('updateProps', {'readOnly': True, 'mode': 'table'})

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

    result = await LocalFilePicker('./', multiple=False)
    ui.notify(f'Selected :  {result}')

    if result is not None:
        if sys.platform.lower() == 'win32' and len(result) > 0:
            result = str(result[0]).replace('\\', '/')
        else:
            result = str(result[0])

        if result != "":
            result = f'./{result}'

        CastAPI.player.set_source(result)
        CastAPI.player.update()


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
                 extension: Optional[str] = None) -> None:

        super().__init__()

        self.drives_toggle = None
        self.path = Path(directory).expanduser()
        if upper_limit is None:
            self.upper_limit = None
        else:
            self.upper_limit = Path(directory if upper_limit == ... else upper_limit).expanduser()
        self.show_hidden_files = show_hidden_files
        self.extension = extension
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
        if sys.platform.lower() == 'win32':
            import win32api
            drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
            self.drives_toggle = ui.toggle(drives, value=drives[0], on_change=self.update_drive)

    def update_drive(self):
        self.path = Path(self.drives_toggle.value).expanduser()
        self.update_grid()

    def update_grid(self) -> None:
        if self.extension:
            paths = list(self.path.glob(f'*{self.extension}'))
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
        self.path = Path(e.args['data']['path'])
        if self.path.is_dir():
            self.update_grid()
        else:
            self.submit([str(self.path)])

    async def _handle_ok(self):
        rows = await self.grid.get_selected_rows()
        self.submit([r['path'] for r in rows])

    def click(self, e: events.GenericEventArguments) -> None:
        self.path = Path(e.args['data']['path'])
        if self.path.suffix.lower() in self.supported_thumb_extensions and self.path.is_file() and self.thumbs:
            ui.notify('Right-click for Preview', position='top')

    async def right_click(self, e: events.GenericEventArguments) -> None:
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
                    ui.button('Close', on_click=thumb.close)
