import asyncio

from nicegui import ui, run
from src.gui.niceutils import edit_protocol, edit_rate_x_y, apply_custom, edit_ip, edit_artnet
from src.utl.utils import CASTUtils as Utils
from str2bool import str2bool
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger')


class CastCenter:
    def __init__(self, iDesktop, iMedia, iCastAPI, it_data_buffer):

        self.Desktop = iDesktop
        self.Media = iMedia
        self.CastAPI = iCastAPI
        self.Queue = it_data_buffer
        self.win = None
        self.win_names = ['** click WINDOWS to refresh **']

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
        self.win_names = await Utils.windows_names()
        self.win.options=self.win_names
        self.win.update()
        ui.notify('Windows refresh finished')


    async def cast_desktop(self,cast_type):
        self.Desktop.stopcast = True
        self.Desktop.preview = False
        if cast_type == 'Desktop':
            self.Desktop.viinput = 'desktop'
        await asyncio.sleep(1)
        self.Desktop.stopcast=False
        self.Desktop.cast(shared_buffer=self.Queue)


    async def setup_ui(self):

        dark = ui.dark_mode(self.CastAPI.dark_mode).bind_value_to(self.CastAPI, 'dark_mode')

        apply_custom()

        if str2bool(cfg_mgr.custom_config['animate_ui']):
            # Add Animate.css to the HTML head
            ui.add_head_html("""
            <link rel="stylesheet" href="assets/css/animate.min.css"/>
            """)

        ui.label('WLEDVideoSync CAST Center').classes('self-center')
        with ui.card().tight().classes('self-center w-full'):
            ui.label(f'DESKTOP : {self.Desktop.host}').classes('self-center')
            with ui.row(wrap=False).classes('w-full'):
                ui.label(f'width: {str(self.Desktop.scale_width)}')
                ui.label(f'height: {str(self.Desktop.scale_height)}')
                card_desktop = ui.card().classes('w-1/3')
                card_desktop.set_visibility(True)
                with card_desktop:
                    with ui.row():
                        monitor = ui.number('Monitor', value=0, min=-1, max=1)
                        monitor.bind_value(self.Desktop, 'monitor_number')
                        desktop_cast = ui.button(icon='cast')
                        desktop_cast.on('click', lambda : self.cast_desktop('Desktop'))

                card_window = ui.card().classes('w-1/3')
                card_window.set_visibility(True)
                with card_window:
                    with ui.row():
                        self.win = ui.select(self.win_names, label='Select Window')
                        self.win.classes('w-40')
                        ui.button(icon='cast')

                card_area = ui.card().classes('w-1/3')
                card_area.set_visibility(True)
                with card_area:
                    with ui.row().classes('self-center'):
                        ui.button('ScreenArea', on_click=lambda: Utils.select_sc_area(self.Desktop)) \
                            .tooltip('Select area from monitor')
                        ui.button(icon='cast')

        with ui.card().tight().classes('self-center w-full'):
            ui.label(f'MEDIA : {self.Media.host}').classes('self-center')
            with ui.row(wrap=False).classes('w-full'):
                ui.label(f'width: {str(self.Media.scale_width)}')
                ui.label(f'height: {str(self.Media.scale_height)}')
                card_desktop = ui.card().tight().classes('w-1/3')
                card_desktop.set_visibility(True)
                with card_desktop:
                    ui.label('card_capture')
                    ui.label('select capture')
                    ui.label('go')

                card_window = ui.card().tight().classes('w-1/3')
                card_window.set_visibility(True)
                with card_window:
                    ui.label('card_video')
                    ui.label('select video')
                    ui.label('go')

                card_area = ui.card().tight().classes('w-1/3')
                card_area.set_visibility(True)
                with card_area:
                    ui.label('card_youtube')
                    ui.label('select yt')
                    ui.label('go')

        with ui.card().tight().classes('self-center w-full'):
            ui.label('TEXT').classes('self-center')
            with ui.row(wrap=False).classes('w-full'):
                card_desktop = ui.card().tight().classes('w-1/3 self-center')
                card_desktop.set_visibility(True)
                with card_desktop:
                    ui.label('card_text')
                    ui.label('enter text')
                    ui.label('go')

                ui.label('select effect')

        with ui.card().tight().classes('self-center w-full'):
            ui.label('TOOLS').classes('self-center')
            with ui.row(wrap=False).classes('w-full'):
                card_tools = ui.card().tight().classes('w-1/3 self-center')
                card_tools.set_visibility(True)
                ui.button('windows', on_click=self.upd_windows)

        # button for right menu show/hide
        with ui.page_sticky(position='top-left', y_offset=10, x_offset=-20):
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat')

        with ui.left_drawer(fixed=False).classes('bg-cyan-700').props('bordered') as left_drawer:
            left_drawer.hide()

            with ui.row().classes('self-center'):
                ui.icon('video_settings', size='md')
                ui.label('SETTINGS')
            ui.separator()
            with ui.row(wrap=False):
                ui.icon('computer', size='xs')
                ui.label('DESKTOP')
            with ui.row():
                await edit_ip(self.Desktop)
                await edit_protocol(self.Desktop)
                with ui.expansion() as desktop_artnet:
                    await edit_artnet(self.Desktop)
                with ui.row():
                    await edit_rate_x_y(self.Desktop)
                    ui.label('')

            ui.separator()
            with ui.row(wrap=False):
                ui.icon('image', size='xs')
                ui.label('MEDIA')
            with ui.row():
                await edit_ip(self.Media)
                await edit_protocol(self.Media)
                with ui.expansion() as media_artnet:
                    await edit_artnet(self.Media)
                with ui.row():
                    await edit_rate_x_y(self.Media)
                    ui.label('')

            ui.separator()
            with ui.row():
                ui.switch('Dark').bind_value(dark)
                ui.button('Validate',icon='verified', on_click=self.validate).classes('self-center')

            ui.separator()
            with ui.row(wrap=False):
                with ui.list().props('bordered'):
                    with ui.slide_item('Expert Mode') as slide_item:
                        with slide_item.right():
                            ui.button('RUN', on_click=lambda: ui.navigate.to('/'))

                with ui.list().props('bordered'):
                    with ui.slide_item('ShutDown') as slide_item:
                        with slide_item.right():
                            ui.button('STOP', on_click=lambda: ui.navigate.to('/'))


if __name__ == "__main__":
    from mainapp import Desktop, Media, CastAPI, t_data_buffer

    cast_app = CastCenter(Desktop, Media, CastAPI, t_data_buffer)

    @ui.page('/')
    async def main_page():
        print('main page')
        await cast_app.setup_ui()

    ui.run(reload=False)