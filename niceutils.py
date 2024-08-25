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

from nicegui import ui
import psutil
from datetime import datetime
from str2bool import str2bool
from utils import CASTUtils as Utils, LocalFilePicker
from cv2utils import CV2Utils
from PIL import Image
import os
import sys


"""
When this env var exist, this mean run from the one-file compressed executable.
Load of the config is not possible, folder config should not exist yet.
This avoid FileNotFoundError.
This env not exist when run from the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    # read config
    # create logger
    logger = Utils.setup_logging('config/logging.ini', 'WLEDLogger.api')

    # load config file
    cast_config = Utils.read_config()

    # config keys
    server_config = cast_config[0]  # server key
    app_config = cast_config[1]  # app key
    color_config = cast_config[2]  # colors key
    custom_config = cast_config[3]  # custom key
    preset_config = cast_config[4]  # presets key


async def system_stats(CastAPI, Desktop, Media ):
    CastAPI.cpu = psutil.cpu_percent(interval=1, percpu=False)
    CastAPI.ram = psutil.virtual_memory().percent
    CastAPI.total_packet = Desktop.total_packet + Media.total_packet
    CastAPI.total_frame = Desktop.total_frame + Media.total_frame

    if str2bool(custom_config['cpu-chart']):
        if CastAPI.cpu_chart is not None:
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
        ui.button('API', on_click=lambda: ui.navigate.to('/docs', new_tab=True), icon='api')


async def sync_button(CastAPI, Media):
    """ Sync Buttons """

    if Media.player_sync is True:
        # VSYNC
        CastAPI.media_button_sync.classes('animate-pulse')
        CastAPI.media_button_sync.props(add="color='gray'")
        if CastAPI.last_type_sync == 'player':
            CastAPI.media_button_sync.props(add="color='red'")
            CastAPI.media_button_sync.text = Media.player_time
        # TSYNC
        CastAPI.slider_button_sync.classes('animate-pulse')
        CastAPI.slider_button_sync.props(add="color='gray'")
        if CastAPI.last_type_sync == 'slider':
            CastAPI.slider_button_sync.props(add="color='red'")
            CastAPI.slider_button_sync.text = Media.player_time

    elif Media.player_sync is False and CastAPI.type_sync != 'none':
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
    """
    refresh cast parameters  on the root page '/'
    :return:
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


async def media_filters(Media):
    #  Filters for Media
    with ui.card().classes('text-sm shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700'):
        ui.label('Filters/Effects Media')
        with ui.row().classes('w-44'):
            ui.checkbox('Flip') \
                .bind_value(Media, 'flip') \
                .classes('w-20')
            ui.number('type', min=0, max=1) \
                .bind_value(Media, 'flip_vh', forward=lambda value: int(value or 0)) \
                .classes('w-20')
            ui.number('W').classes('w-20').bind_value(Media, 'scale_width', forward=lambda value: int(value or 8))
            ui.number('H').classes('w-20').bind_value(Media, 'scale_height', forward=lambda value: int(value or 8))
            with ui.row().classes('w-44').style('justify-content: flex-end'):
                ui.label('gamma')
                ui.slider(min=0.01, max=4, step=0.01) \
                    .props('label-always') \
                    .bind_value(Media, 'gamma')
            with ui.column(wrap=True):
                with ui.row():
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-red') \
                            .bind_value(Media, 'balance_r')
                        ui.label('R').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-green') \
                            .bind_value(Media, 'balance_g')
                        ui.label('G').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-blue') \
                            .bind_value(Media, 'balance_b')
                        ui.label('B').classes('self-center')
                ui.button('reset', on_click=lambda: reset_rgb(Media)).classes('self-center')

    with ui.card().classes('text-sm shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]'):
        with ui.row().classes('w-20').style('justify-content: flex-end'):
            ui.label('saturation')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Media, 'saturation')
            ui.label('brightness').classes('text-right')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Media, 'brightness')
            ui.label('contrast')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Media, 'contrast')
            ui.label('sharpen')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Media, 'sharpen')
            ui.checkbox('auto') \
                .bind_value(Media, 'auto_bright', forward=lambda value: value) \
                .tooltip('Auto bri/contrast')
            ui.slider(min=0, max=100, step=1) \
                .props('label-always') \
                .bind_value(Media, 'clip_hist_percent')


async def desktop_filters(Desktop):
    """ desktop filter page creation"""

    with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset] bg-cyan-700'):
        ui.label('Filters/Effects Desktop')
        with ui.row().classes('w-44'):
            ui.checkbox('Flip') \
                .bind_value(Desktop, 'flip') \
                .classes('w-20')
            ui.number('type', min=0, max=1) \
                .bind_value(Desktop, 'flip_vh', forward=lambda value: int(value or 0)) \
                .classes('w-20')
            ui.number('W').classes('w-20').bind_value(Desktop, 'scale_width', forward=lambda value: int(value or 8))
            ui.number('H').classes('w-20').bind_value(Desktop, 'scale_height',
                                                      forward=lambda value: int(value or 8))
            with ui.row().classes('w-44').style('justify-content: flex-end'):
                ui.label('gamma')
                ui.slider(min=0.01, max=4, step=0.01) \
                    .props('label-always') \
                    .bind_value(Desktop, 'gamma')
            with ui.column(wrap=True):
                with ui.row():
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-red') \
                            .bind_value(Desktop, 'balance_r')
                        ui.label('R').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-green') \
                            .bind_value(Desktop, 'balance_g')
                        ui.label('G').classes('self-center')
                    with ui.column():
                        ui.knob(0, min=0, max=255, step=1, show_value=True).classes('bg-blue') \
                            .bind_value(Desktop, 'balance_b')
                        ui.label('B').classes('self-center')
                ui.button('reset', on_click=lambda: reset_rgb(Desktop)).classes('self-center')

    with ui.card().classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]'):
        with ui.row().classes('w-20').style('justify-content: flex-end'):
            ui.label('saturation')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Desktop, 'saturation')
            ui.label('brightness')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Desktop, 'brightness')
            ui.label('contrast')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Desktop, 'contrast')
            ui.label('sharpen')
            ui.slider(min=0, max=100, step=1, value=0) \
                .props('label-always') \
                .bind_value(Desktop, 'sharpen')
            ui.checkbox('auto') \
                .bind_value(Desktop, 'auto_bright', forward=lambda value: value) \
                .tooltip('Auto bri/contrast')
            ui.slider(min=0, max=100, step=1) \
                .props('label-always') \
                .bind_value(Desktop, 'clip_hist_percent')


async def create_cpu_chart(CastAPI):
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
    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': CV2Utils.get_media_info(player_media)}}) \
            .run_editor_method('updateProps', {'readOnly': True, 'mode': 'table'})


async def player_url_info(player_url):
    """ Grab YouTube information from an Url """

    async def yt_search():
        await ui.context.client.connected()
        with ui.dialog() as dialog:
            dialog.open()
            editor = ui.json_editor({'content': {'json': await Utils.list_yt_formats(player_url)}}) \
                .run_editor_method('updateProps', {'readOnly': True, 'mode': 'tree'})

    ui.notify('Grab info from YT ...')
    ui.timer(.1, yt_search, once=True)


async def display_formats():
    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.list_av_formats()}}) \
            .run_editor_method('updateProps', {'readOnly': True})


async def display_codecs():
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
                ui.button(text=str(i) + ':size:' + str(w) + 'x' + str(h), icon='tag') \
                    .props('flat fab color=white') \
                    .classes('absolute top-0 left-0 m-2') \
                    .tooltip('Image Number')


async def multi_preview(class_name):
    """
    Generate matrix image preview for multicast
    :return:
    """
    dialog = ui.dialog().style('width: 200px')
    with dialog:
        grid_col = ''
        for c in range(class_name.cast_x):
            grid_col += '1fr '
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
                        ui.label('No: ' + str(class_name.cast_devices[i][0]))
                        if Utils.validate_ip_address(str(class_name.cast_devices[i][1])):
                            text_decoration = "color: green; text-decoration: underline"
                        else:
                            text_decoration = "color: red; text-decoration: red wavy underline"

                        ui.link('IP  :  ' + str(class_name.cast_devices[i][1]),
                                'http://' + str(class_name.cast_devices[i][1]),
                                new_tab=True).style(text_decoration)
        ui.button('Close', on_click=dialog.close, color='red')
    ui.button('DEVICE', icon='preview', on_click=dialog.open).tooltip('View Cast devices')


async def player_pick_file(CastAPI) -> None:
    """ Select file to read for video CastAPI.player"""

    result = await LocalFilePicker('./', multiple=False)
    ui.notify(f'Selected :  {result}')

    if result is not None:
        if sys.platform.lower() == 'win32':
            result = str(result[0]).replace('\\', '/')

        result = './' + result

        CastAPI.player.set_source(result)
        CastAPI.player.update()

