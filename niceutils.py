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
import concurrent_log_handler

from nicegui import ui, events
import psutil
from datetime import datetime
from str2bool import str2bool

from utils import CASTUtils as Utils
from cv2utils import CV2Utils
from cv2utils import VideoThumbnailExtractor
from PIL import Image
import os
import sys

from pathlib import Path
from typing import Optional

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


async def system_stats(CastAPI, Desktop, Media):
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
        if str2bool(app_config['fastapi_docs']):
            ui.button('API', on_click=lambda: ui.navigate.to('/docs', new_tab=True), icon='api')
        ui.icon('info', size='sm').on('click', lambda: app_info()).style('cursor:pointer')


def app_info():
    """ display app , compile version """

    with ui.dialog() as dialog:
        dialog.open()
        editor = ui.json_editor({'content': {'json': Utils.compile_info()}}) \
            .run_editor_method('updateProps', {'readOnly': True})


async def sync_button(CastAPI, Media):
    """ Sync Buttons """

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
    """ Select file to read for video CastAPI.player """

    result = await LocalFilePicker('./', multiple=False)
    ui.notify(f'Selected :  {result}')

    if result is not None:
        if sys.platform.lower() == 'win32' and len(result) > 0:
            result = str(result[0]).replace('\\', '/')

        if len(result) > 0:
            result = './' + result

        CastAPI.player.set_source(result)
        CastAPI.player.update()


async def generate_actions_to_cast(class_name, class_threads, action_to_casts, info_data):
    """ Generate expansion for each cast with icon/action """

    casts_row = ui.row()
    with (casts_row):
        for item_th in class_threads:
            item_exp = ui.expansion(item_th, icon='cast') \
                .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')
            with item_exp:
                with ui.row():
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
                                                                              action='close_preview',
                                                                              params='',
                                                                              clear=False,
                                                                              execute=True)
                              ).classes('shadow-lg').tooltip('Stop Preview')
                    ui.button(icon='preview',
                              on_click=lambda item_v=item_th: action_to_casts(class_name=class_name,
                                                                              cast_name=item_v,
                                                                              action='open_preview',
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

                editor = ui.json_editor({'content': {'json': info_data[item_th]["data"]}}) \
                    .run_editor_method('updateProps', {'readOnly': True})


class LocalFilePicker(ui.dialog):
    """Local File Picker

    This is  simple file picker that allows you to select a file from the local filesystem where NiceGUI is running.
    Right-click on a file will display image if available.

    :param directory: The directory to start in.
    :param upper_limit: The directory to stop at (None: no limit, default: same as the starting directory).
    :param multiple: Whether to allow multiple files to be selected.
    :param show_hidden_files: Whether to show hidden files.
    :param thumbs : generate thumbnails
    """

    def __init__(self, directory: str, *,
                 upper_limit: Optional[str] = ...,
                 multiple: bool = False, show_hidden_files: bool = False, thumbs: bool = True) -> None:

        super().__init__()

        self.drives_toggle = None
        self.path = Path(directory).expanduser()
        if upper_limit is None:
            self.upper_limit = None
        else:
            self.upper_limit = Path(directory if upper_limit == ... else upper_limit).expanduser()
        self.show_hidden_files = show_hidden_files

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
        if self.path.is_file() and self.thumbs:
            ui.notify('Right-click for Preview', position='top')

    async def right_click(self, e: events.GenericEventArguments) -> None:
        self.path = Path(e.args['data']['path'])
        if self.path.is_file() and self.thumbs:
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
