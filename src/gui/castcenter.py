import asyncio

import src.gui.tkinter_fonts
from src.gui.tkinter_fonts import *
from nicegui import ui, run, app
from src.gui.niceutils import edit_protocol, edit_rate_x_y, edit_ip, edit_artnet, apply_custom
from src.gui.niceutils import LocalFilePicker, YtSearch
from src.utl.utils import CASTUtils as Utils
from src.utl.winutil import windows_names
from str2bool import str2bool
from src.gui.niceutils import AnimatedElement as Animate
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger')

class CastCenter:
    def __init__(self, Desktop, Media, CastAPI, t_data_buffer):

        self.Desktop = Desktop
        self.Media = Media
        self.CastAPI = CastAPI
        self.Queue = t_data_buffer
        self.win = None
        self.device = None
        self.video = None
        self.yt_area = None
        self.yt_input = None
        self.desktop_status = None
        self.media_status = None

    async def validate(self):
        await CastCenter.validate_data(self.Media)
        await CastCenter.validate_data(self.Desktop)
        ui.navigate.reload()

    @staticmethod
    async def validate_data(class_obj):
        # retrieve matrix setup from wled and set w/h
        if class_obj.wled:
            class_obj.scale_width, class_obj.scale_height = await Utils.get_wled_matrix_dimensions(class_obj.host)


    async def upd_windows(self):
        self.win.options = await windows_names()
        self.win.update()
        ui.notify('Windows refresh finished')

    async def upd_devices(self):
        self.device.options = await Utils.video_device_list()
        self.device.update()
        ui.notify('Device refresh finished')

    async def pick_file(self):
        """ Select file to read as video """

        result = await LocalFilePicker(cfg_mgr.app_root_path('/'), multiple=False)
        ui.notify(f'Selected :  {result}')

        if result is not None:
            result = str(result[0])
            self.video.set_value(result)
            self.video.update()

    async def search_yt(self):
        self.yt_area.clear()
        self.yt_area.set_visibility(True)
        self.yt_area.classes('w-full border')
        with self.yt_area:
            YtSearch(self.yt_input, True)

    @staticmethod
    async def view_fonts():
        await run.cpu_bound(src.gui.tkinter_fonts.run)

    async def cast_class(self,class_obj, cast_type):
        class_name = 'unknown'
        if 'Desktop' in str(class_obj):
            class_name = 'Desktop'
        elif 'Media' in str(class_obj):
            class_name = 'Media'

        # stop running cast
        class_obj.stopcast = True
        # select cast
        if class_name == 'Desktop':

            await self.cast_desktop(cast_type)

        elif class_name == 'Media':

            await self.cast_media(cast_type)
        #
        await asyncio.sleep(1)
        # run new cast
        class_obj.stopcast=False
        class_obj.cast(shared_buffer=self.Queue)

    async def cast_desktop(self,cast_type):
        # select cast
        if cast_type == 'Desktop':
            self.Desktop.viinput = 'desktop'
        elif cast_type == 'Window':
            self.Desktop.viinput = f'win={self.win.value}'
        elif cast_type == 'Area':
            self.Desktop.viinput = 'area'
        else:
            cfg_mgr.logger.error('Error on cast_type')

        self.desktop_status.props('color="red"')


    async def cast_media(self,cast_type):
        # select cast
        if cast_type == 'Capture':
            try:
                self.Media.viinput = self.device.value[2]
            except Exception as er:
                cfg_mgr.logger.error(f'Error on device: {er}')
        elif cast_type == 'Video':
            self.Media.viinput = self.video.value
        elif cast_type == 'Youtube':
            # custom_format = cfg_mgr.custom_config['yt_format']
            yt_url = await Utils.get_yt_video_url(video_url=self.yt_input.value,iformat="best")
            self.Media.viinput = yt_url
        else:
            cfg_mgr.logger.error('Error on cast_type')

    async def center_timer_action(self):

        if self.Desktop.count > 0:
            self.desktop_status.props('color="red"')
        elif self.Desktop.stopcast:
            self.desktop_status.props('color="yellow"')
        else:
            self.desktop_status.props('color="green"')

        if self.Media.count > 0:
            self.media_status.props('color="red"')
        elif self.Media.stopcast:
            self.media_status.props('color="yellow"')
        else:
            self.media_status.props('color="green"')

    async def setup_ui(self):

        dark = ui.dark_mode(self.CastAPI.dark_mode).bind_value_to(self.CastAPI, 'dark_mode')

        apply_custom()

        if str2bool(cfg_mgr.custom_config['animate_ui']):
            # Add Animate.css to the HTML head
            ui.add_head_html("""
            <link rel="stylesheet" href="assets/css/animate.min.css"/>
            """)

        """
        timer created on main page run to refresh datas
        """
        ui.timer(int(cfg_mgr.app_config['timer']), callback=self.center_timer_action)
        #
        """
        Center page creation
        """
        ui.label('WLEDVideoSync CAST Center').classes('self-center mb-4 text-red-900 text-2xl font-extrabold  dark:text-white md:text-4xl lg:text-5xl')
        with ui.card().tight().classes('self-center w-full'):
            with ui.row().classes('self-center'):
                self.desktop_status = ui.icon('cast_connected', size='sm', color='green')
                ui.label(f'DESKTOP : {self.Desktop.host}').classes('self-center')
            with ui.row().classes('self-center'):
                ui.label(f'width: {str(self.Desktop.scale_width)}')
                ui.label(f'height: {str(self.Desktop.scale_height)}')

            with ui.row(wrap=False).classes('w-full'):
                card_desktop = ui.card().classes('w-1/3')
                card_desktop.props('flat')
                card_desktop.set_visibility(True)
                with card_desktop:
                    ui.image('assets/desktop.png').style('width:100px;height:100px;').classes('self-center')
                    with ui.row().classes('self-center'):
                        monitor = ui.number('Monitor', value=0, min=-1, max=1)
                        monitor.bind_value(self.Desktop, 'monitor_number')
                        desktop_cast = ui.button(icon='cast').classes('m-4')
                        desktop_cast.on('click', lambda : self.cast_class(self.Desktop, 'Desktop'))

                ui.separator().style('width: 2px; height: 200px; background-color: #2E4C69;')

                with ui.column().classes('w-1/3'):
                    with ui.row().classes('w-full'):
                        ui.space()
                        ui.icon('cancel_presentation', size='lg', color='red') \
                            .on('click', lambda: setattr(self.Desktop, 'stopcast', True)) \
                            .style('cursor: pointer')

                    card_area = ui.card().classes('w-full')
                    card_area.set_visibility(True)
                    with card_area:

                        if str2bool(cfg_mgr.custom_config['animate_ui']):
                            row_area_anim = Animate(ui.row, animation_name_in='backInDown', duration=1)
                            row_area = row_area_anim.create_element()
                        else:
                            row_area = ui.row()

                        with row_area.classes('self-center'):
                            ui.button('ScreenArea', on_click=lambda: Utils.select_sc_area(self.Desktop)) \
                                .tooltip('Select area from monitor')
                            area_cast = ui.button(icon='cast')
                            area_cast.on('click', lambda : self.cast_class(self.Desktop, 'Area'))

                ui.separator().style('width: 2px; height: 200px; background-color: #2E4C69;')

                card_window = ui.card().classes('w-1/3')
                card_window.props('flat')
                card_window.set_visibility(True)
                with card_window:
                    ui.image('assets/windows.png').style('width:100px;height:100px;').classes('self-center')
                    with ui.row().classes('self-center'):
                        self.win = ui.select(['** click WINDOWS to refresh **'], label='Select Window')
                        self.win.classes('w-40')
                        win_cast = ui.button(icon='cast').classes('m-4')
                        win_cast.on('click', lambda : self.cast_class(self.Desktop, 'Window'))

        with ui.card().tight().classes('self-center w-full'):
            with ui.row().classes('self-center'):
                self.media_status = ui.icon('cast_connected', size='sm', color='green')
                ui.label(f'MEDIA : {self.Media.host}').classes('self-center')
            with ui.row().classes('self-center'):
                ui.label(f'width: {str(self.Media.scale_width)}')
                ui.label(f'height: {str(self.Media.scale_height)}')

            with ui.row(wrap=False).classes('w-full'):
                card_capture = ui.card().classes('w-1/3')
                card_capture.props('flat')
                card_capture.set_visibility(True)
                with card_capture:
                    ui.image('assets/camera.png').style('width:100px;height:100px;').classes('self-center')
                    with ui.row().classes('self-center'):
                        self.device = ui.select(['** click DEVICES to refresh **'], label='Select Device')
                        self.device.classes('w-40')
                        capture_cast = ui.button(icon='cast').classes('m-4')
                        capture_cast.on('click', lambda : self.cast_class(self.Media, 'Capture'))

                ui.separator().style('width: 2px; height: 200px; background-color: #2E4C69;')

                with ui.column().classes('w-1/3'):
                    with ui.row().classes('w-full'):
                        ui.space()
                        ui.icon('cancel_presentation', size='lg', color='red') \
                            .on('click', lambda: setattr(self.Media, 'stopcast', True)) \
                            .style('cursor: pointer')

                    card_video = ui.card().classes('w-full')
                    card_video.set_visibility(True)
                    with card_video:

                        if str2bool(cfg_mgr.custom_config['animate_ui']):
                            row_video_anim = Animate(ui.row, animation_name_in='backInUp', duration=1)
                            row_video = row_video_anim.create_element()
                        else:
                            row_video = ui.row()

                        with row_video.classes('self-center'):
                            ui.icon('folder',size='xl',color='yellow').on('click',lambda: self.pick_file()).style('cursor: pointer').classes('m-4')
                            self.video = ui.input('enter url / file name ')
                            ui.number('repeat',min=-1,max=99, value=self.Media.repeat).bind_value(self.Media,'repeat')
                            video_cast = ui.button(icon='cast').classes('m-4')
                            video_cast.on('click', lambda : self.cast_class(self.Media, 'Video'))

                ui.separator().style('width: 2px; height: 200px; background-color: #2E4C69;')

                card_yt = ui.card().tight().classes('w-1/3')
                card_yt.props('flat')
                card_yt.set_visibility(True)
                with card_yt:
                    ui.image('assets/youtube.png').style('width:100px;height:100px;').classes('self-center')
                    with ui.row(wrap=False).classes('self-center'):
                        yt_icon = ui.icon('youtube_searched_for',size='xl', color='indigo-3').classes('m-4')
                        yt_icon.style('cursor:pointer')
                        yt_icon.on('click', lambda: self.search_yt())
                        self.yt_input = ui.input('enter YT url')
                        yt_cancel = ui.icon('disabled_visible',size='sm', color='red').classes('m-4')
                        yt_cancel.style('cursor:pointer')
                        yt_cancel.on('click', lambda: self.yt_area.set_visibility(False))
                        yt_cast = ui.button(icon='cast').classes('m-4')
                        yt_cast.on('click', lambda : self.cast_class(self.Media, 'Youtube'))

        self.yt_area = ui.scroll_area()
        self.yt_area.set_visibility(False)

        with ui.card().tight().classes('self-center w-full'):
            ui.label('TEXT').classes('self-center')
            with ui.row(wrap=False).classes('w-full'):
                card_desktop = ui.card().tight().classes('w-1/3 self-center')
                card_desktop.set_visibility(True)
                with card_desktop:
                    txt_input = ui.input('Enter some text', placeholder='text enter').classes('w-full')
                ui.label('select effect')

        with ui.card().classes('self-center w-full'):
            ui.label('TOOLS').classes('self-center')
            with ui.row(wrap=False).classes('w-full self-center'):
                tool_capture = ui.card().tight().classes('w-1/3')
                tool_capture.set_visibility(True)
                tool_capture.props('flat')
                with tool_capture:
                    ui.button('Devices', on_click=self.upd_devices)

                ui.separator().style('width: 2px; height: 40px; background-color: red;')

                tool_text = ui.card().tight().classes('w-1/3')
                tool_text.set_visibility(True)
                tool_text.props('flat')
                with tool_text:
                    ui.button('Fonts', on_click=CastCenter.view_fonts)

                ui.separator().style('width: 2px; height: 40px; background-color: red;')

                tool_win = ui.card().tight().classes('w-1/3')
                tool_win.set_visibility(True)
                tool_win.props('flat')
                with tool_win:
                    ui.button('Windows', on_click=self.upd_windows)

        # button for right menu show/hide
        with ui.page_sticky(position='top-left', y_offset=10, x_offset=-20):
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').classes('dark:bg-cyan-700').props('flat')

        with ui.left_drawer(fixed=False).classes('bg-cyan-700').props('bordered') as left_drawer:
            left_drawer.hide()

            with ui.row().classes('self-center'):
                ui.icon('video_settings', size='xl')
                ui.label('SETTINGS')
            ui.separator().props(add='size=8px')

            with ui.row(wrap=False):
                ui.icon('computer', size='lg')
                ui.label('DESKTOP')
                ui.checkbox('Preview').bind_value(self.Desktop,'preview')
            capture_methode = ui.select(options=['av','mss'], label='Capture Method').style(add='width:120px')
            capture_methode.bind_value(self.Desktop,'capture_methode')

            ui.separator()
            with ui.row():
                await edit_ip(self.Desktop)
                await edit_protocol(self.Desktop)
                with ui.expansion() as desktop_artnet:
                    await edit_artnet(self.Desktop)
                with ui.row():
                    await edit_rate_x_y(self.Desktop)
                    ui.label('')

            ui.separator().props(add='size=8px')
            with ui.row(wrap=False):
                ui.icon('image', size='lg')
                ui.label('MEDIA')
                ui.checkbox('Preview').bind_value(self.Media,'preview')

            ui.separator()
            with ui.row():
                await edit_ip(self.Media)
                await edit_protocol(self.Media)
                with ui.expansion() as media_artnet:
                    await edit_artnet(self.Media)
                with ui.row():
                    await edit_rate_x_y(self.Media)
                    ui.label('')

            ui.separator().props(add='size=8px')
            with ui.row():
                ui.switch('Dark').bind_value(dark)
                ui.button('Validate',icon='verified', on_click=self.validate).classes('self-center')

            ui.separator().props(add='size=8px')
            with ui.row(wrap=False):
                with ui.list().props('bordered'):
                    with ui.slide_item('Expert Mode') as slide_item:
                        with slide_item.right():
                            root_page_url = Utils.root_page()
                            if root_page_url == '/Cast-Center':
                                go_to_url = '/main'
                            else:
                                go_to_url = '/'
                            ui.button('RUN', on_click=lambda: ui.navigate.to(go_to_url))

                with ui.list().props('bordered'):
                    with ui.slide_item('ShutDown') as slide_item:
                        with slide_item.right():
                            ui.button('STOP', on_click=lambda: app.shutdown())


if __name__ == "__main__":
    from mainapp import Desktop as Dk, Media as Md, CastAPI as Api, t_data_buffer as queue
    from nicegui import app

    app.add_static_files('/assets',cfg_mgr.app_root_path('assets'))
    cast_app = CastCenter(Dk, Md, Api, queue)

    print('start main')
    @ui.page('/')
    async def main_page():
        print('main page')
        await cast_app.setup_ui()

    ui.run(reload=False)

    print('End main')
