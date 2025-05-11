import traceback
import re
import urllib.parse
import time

from datetime import datetime
from nicegui import ui, run
from str2bool import str2bool
from asyncio import create_task, sleep
from wled import WLED

import src.gui.niceutils as nice
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils
from src.gui.niceutils import YtSearch
from src.gui.niceutils import AnimatedElement as Animate

from configmanager import cfg_mgr, LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.player')
player_logger = logger_manager.logger

class VideoPlayer:
    def __init__(self, Media, CastAPI, t_data_buffer):
        self.Media = Media
        self.CastAPI = CastAPI
        self.queue = t_data_buffer

    async def youtube_clear_search(self):
        """
        Clear search results
        """
        for area in self.CastAPI.search_areas:
            try:
                if str2bool(cfg_mgr.custom_config['animate_ui']):
                    animated_area = Animate(area, animation_name_out="backOutUp", duration=1)
                    animated_area.delete_element(area)
                else:
                    area.delete()
            except Exception as e:
                player_logger.error(traceback.format_exc())
                player_logger.error(f'Search area does not exist: {e}')
        self.CastAPI.search_areas = []

    async def youtube_search(self, player_url):
        """
        display search result from pytube
        player_url :  ui.input from the player to be updated
        """
        anime = False
        if str2bool(cfg_mgr.custom_config['animate_ui']):
            animated_yt_area = Animate(ui.scroll_area, animation_name_in="backInDown", duration=1.5)
            yt_area = animated_yt_area.create_element()
            anime = True
        else:
            yt_area = ui.scroll_area()

        yt_area.bind_visibility_from(self.CastAPI.player)
        yt_area.classes('w-full border')
        self.CastAPI.search_areas.append(yt_area)
        with yt_area:
            YtSearch(player_url, anime)

    async def player_cast(self,source):
        """ Cast from video CastAPI.player only for Media """

        media_info = await CV2Utils.get_media_info(source)
        if self.Media.stopcast:
            ui.notify(f'Cast NOT allowed to run from : {source}', type='warning')
        else:
            self.Media.viinput = source
            self.Media.rate = int(media_info['CAP_PROP_FPS'])
            ui.notify(f'Cast running from : {source}')
            self.Media.cast(shared_buffer=self.queue)
        self.CastAPI.player.play()

    def reset_sync(self):
        """ Reset player sync value to default """

        self.Media.cast_sync = False
        self.Media.auto_sync_delay = 30
        self.Media.add_all_sync_delay = 0
        player_logger.info('Reset Sync')

    async def slider_sync(self):
        """ Set Sync Cast to True """

        current_time = self.CastAPI.video_slider.value
        ui.notify(f'Slider Time : {current_time}')
        # set time
        self.Media.sync_to_time = current_time * 1000
        self.Media.cast_sync = True
        self.CastAPI.type_sync = 'slider'
        self.CastAPI.last_type_sync = 'slider'
        # gui update
        self.CastAPI.slider_button_sync.props(add="color=red")
        self.CastAPI.slider_button_sync.text = current_time
        self.CastAPI.slider_button_sync.classes('animate-pulse')
        self.CastAPI.media_button_sync.props(remove="color=red")
        self.CastAPI.media_button_sync.text = "VSYNC"

    async def player_sync(self):
        """ Set Sync cast to True """

        # client need to be connected
        await ui.context.client.connected()
        current_time = round(await ui.run_javascript("document.querySelector('video').currentTime", timeout=2))
        ui.notify(f'Player Time : {current_time}')
        # set time
        self.Media.sync_to_time = current_time * 1000
        self.Media.cast_sync = True
        self.CastAPI.type_sync = 'player'
        self.CastAPI.last_type_sync = 'player'
        # gui update
        self.CastAPI.media_button_sync.props(add="color=red")
        self.CastAPI.media_button_sync.text = current_time
        self.CastAPI.media_button_sync.classes('animate-pulse')
        self.CastAPI.slider_button_sync.props(remove="color=red")
        self.CastAPI.slider_button_sync.text = "TSYNC"

    def slider_time(self,current_time):
        """ Set player time for Cast """
        if self.CastAPI.type_sync == 'slider':
            self.Media.sync_to_time = current_time * 1000

    async def get_player_time(self):
        """
        Retrieve current play time from the Player
        Set player time for Cast to Sync & current frame number
        """
        if self.CastAPI.type_sync == 'player':
            await ui.context.client.connected()
            current_time = float(await ui.run_javascript("document.querySelector('video').currentTime", timeout=2))
            self.Media.sync_to_time = current_time * 1000
            # Calculate current frame number
            current_frame = int(current_time * self.CastAPI.video_fps)
            self.CastAPI.current_frame = current_frame

    async def player_duration(self):
        """
        Return current duration time from the Player
        Set slider max value to video duration
        """
        await ui.context.client.connected()
        current_duration = await ui.run_javascript("document.querySelector('video').duration", timeout=2)
        player_logger.info(f'Video duration:{current_duration}')
        self.Media.player_duration = current_duration
        self.CastAPI.video_slider._props["max"] = current_duration
        self.CastAPI.video_slider.update()

    async def bar_get_size(self):
        """ Read data from YT download, loop until no more data to download """
        while Utils.yt_file_size_remain_bytes != 0:
            self.CastAPI.progress_bar.value = 1 - (Utils.yt_file_size_remain_bytes / Utils.yt_file_size_bytes)
            self.CastAPI.progress_bar.update()
            await sleep(.1)

    async def update_video_information(self):
        video_info = await CV2Utils.get_media_info(self.CastAPI.player.source)
        self.CastAPI.video_fps = int(video_info['CAP_PROP_FPS'])
        self.CastAPI.video_frames = int(video_info['CAP_PROP_FRAME_COUNT'])

    async def video_player_page(self):
        """
        Video player
        """
    
        async def player_video_info():
            # video info
            await self.update_video_information()
    
            if str2bool(cfg_mgr.custom_config['gif_enabled']):
                # set gif info
                start_gif.max = self.CastAPI.video_frames
                end_gif.max = self.CastAPI.video_frames
                end_gif.set_value(self.CastAPI.video_frames)
    
        async def player_set_file():
            await nice.player_pick_file(self.CastAPI)
            await player_video_info()
    
        async def validate_player_url():
            url_path = False
            #
            parsed_url = urllib.parse.urlparse(video_img_url.value)
            if parsed_url.scheme and not re.match(r'^[a-zA-Z]$', parsed_url.scheme):  # Check for valid URL scheme (not drive letter)
                url_path = True
    
            if url_path and 'youtube' in parsed_url.netloc.lower():
                yt_format = cfg_mgr.custom_config['yt_format']
                yt_url = await Utils.get_yt_video_url(video_img_url.value, iformat=yt_format)
    
                player_logger.info(f'Player set to : {yt_url}')
    
                # set video player self.Media
                self.CastAPI.player.set_source(yt_url)
                self.CastAPI.player.update()
    
                await player_video_info()
    
    
        async def player_set_url(url):
            """ Download video/image from Web url or local path
    
            url: video url
            start_in : ui.input for frame start
            end_in : ui.input for frame end
            """
    
            #  this can be Web or local
            url_path = False
            #
            encoded_str = url
            decoded_str = urllib.parse.unquote(encoded_str)
            #
            parsed_url = urllib.parse.urlparse(url)
            if parsed_url.scheme and not re.match(r'^[a-zA-Z]$', parsed_url.scheme):  # Check for valid URL scheme (not drive letter)
                url_path = True
            #
            # init value for progress bar
            self.CastAPI.progress_bar.value = 0
            self.CastAPI.progress_bar.update()
            #
            # if this is Web url
            if url_path:
                # check if YT Url, so will download to self.Media
                if 'youtube' in parsed_url.netloc.lower():
    
                    # this will run async loop in background and continue...
                    create_task(self.bar_get_size())
                    # wait YT download finished
                    yt_video_name = await Utils.youtube_download(url, interactive=True)
                    # if no error, set local YT file name to video player
                    if yt_video_name != '':
                        decoded_str = yt_video_name
    
                # check if this is an image, so will download to self.Media
                elif await Utils.is_image_url(url):
    
                    # generate a unique name
                    # Get the current date and time
                    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # Format the unique name with prefix, date, time, and extension
                    # hardcoded jpg format, this need to be reviewed
                    image_name = f"image-tmp_{current_time}.jpg"
    
                    result = await Utils.download_image(cfg_mgr.app_root_path('media'), url, image_name)
                    if result:
                        decoded_str = cfg_mgr.app_root_path(f'media/{image_name}')
                else:
                    player_logger.debug('No yt or image url')
            #
            ui.notify(f'Player set to : {decoded_str}')
            player_logger.debug(f'Player set to : {decoded_str}')
    
            # put max value to progress bar
            self.CastAPI.progress_bar.value = 1
            self.CastAPI.progress_bar.update()
    
            # set video player self.Media
            self.CastAPI.player.set_source(decoded_str)
            self.CastAPI.player.update()
    
            await player_video_info()
    
        async def gif_to_wled():
            """
            Upload GIF to Wled device
            :return:
            """
            video_in = self.CastAPI.player.source
            ui.notify('Start GIF Uploading')
            send_gif.props(add='loading')
            gif_to_upload = cfg_mgr.app_root_path(f'media/gif/{Utils.extract_filename(video_in)}_.gif')
            await run.io_bound(lambda: Utils.wled_upload_gif_file(self.Media.host, gif_to_upload))
            led = WLED(self.Media.host)
            try:
                presets = await led.request('/presets.json')
                preset_number = max(int(key) for key in presets.keys()) + 1
                preset_name = f'WLEDVideoSync-{preset_number}'
                segment_name = Utils.wled_name_format(Utils.extract_filename(gif_to_upload))
                # set segment name as gif file
                wled_data={"on":1,"bri":10,"transition":0,"bs":0,"mainseg":0,"seg":[{"id":0,"n":f"{segment_name}","fx":53}]}
                await led.request('/json/state', method='POST', data=wled_data)
                # create preset
                await led.request('/json/state', method='POST', data={"ib":1,
                                                                      "sb":1,
                                                                      "sc":0,
                                                                      "psave":preset_number,
                                                                      "n":preset_name,
                                                                      "v":1,
                                                                      "time":time.time()})
            except Exception as er:
                player_logger.error(f'Error in WLED upload: {er}')
            finally:
                await led.close()
    
            send_gif.props(remove='loading')
            ui.notify('End GIF Uploading')
    
        async def open_gif():
            sync_buttons.set_visibility(False)
            gif_buttons.set_visibility(True)
    
        async def close_gif():
            sync_buttons.set_visibility(True)
            gif_buttons.set_visibility(False)
    
        async def create_gif():
            video_in = self.CastAPI.player.source
            gen_gif.props(add='loading')
            if self.Media.wled:
                send_gif.disable()
            # generate a unique name
            # Get the current date and time
            # current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            gif_out = cfg_mgr.app_root_path(f'media/gif/{Utils.extract_filename(video_in)}_.gif')
            ui.notify(f'Generating GIF : {gif_out} ...')
            await run.io_bound(lambda: CV2Utils.video_to_gif(video_in,gif_out,
                                                             self.Media.rate,
                                                             int(start_gif.value),
                                                             int(end_gif.value),
                                                             self.Media.scale_width,
                                                             self.Media.scale_height))
            ui.notify('GIF finished !')
            if self.Media.wled:
                send_gif.enable()
                send_gif.props(remove='loading')
            gen_gif.props(remove='loading')
    
        async def manage_visibility(visible):
            self.CastAPI.player.set_visibility(visible)
            await nice.animate_wled_image(self.CastAPI, visible)
    
        if str2bool(cfg_mgr.custom_config['animate_ui']):
            center_card_anim = Animate(ui.card, animation_name_in='fadeInUp', duration=1)
            center_card = center_card_anim.create_element()
        else:
            center_card = ui.card()
    
        center_card.classes('self-center w-2/3 bg-gray-500')
        with center_card:
            video_file = cfg_mgr.app_root_path(cfg_mgr.app_config["video_file"])
            self.CastAPI.player = ui.video(src=video_file).classes('self-center')
            self.CastAPI.player.on('ended', lambda _: ui.notify('Video playback completed.'))
            self.CastAPI.player.on('timeupdate', lambda: self.get_player_time())
            self.CastAPI.player.on('durationchange', lambda: self.player_duration())
            self.CastAPI.player.set_visibility(True)
    
            await self.update_video_information()
    
            with ui.row(wrap=False).classes('self-center'):
                ui.label() \
                    .bind_text_from(self.Media, 'sync_to_time') \
                    .classes('self-center bg-slate-400') \
                    .bind_visibility_from(self.CastAPI.player)
                ui.label('+').bind_visibility_from(self.CastAPI.player)
                ui.label() \
                    .bind_text_from(self.Media, 'add_all_sync_delay') \
                    .classes('self-center bg-slate-400') \
                    .bind_visibility_from(self.CastAPI.player)
            self.CastAPI.video_slider = ui.slider(min=0, max=7200, step=1, value=0,
                                             on_change=lambda var: self.slider_time(var.value)).props('label-always') \
                .bind_visibility_from(self.CastAPI.player)
    
            with ui.row() as sync_buttons:
                sync_buttons.classes('self-center')
                media_frame = ui.knob(0, min=-1000, max=1000, step=1, show_value=True).classes('bg-gray')
                media_frame.bind_value(self.Media, 'cast_skip_frames')
                media_frame.tooltip('+ / - frames to CAST')
                media_frame.bind_visibility_from(self.CastAPI.player)
    
                self.CastAPI.media_button_sync = ui.button('VSync', on_click=self.player_sync, color='green') \
                    .tooltip('Sync Cast with Video Player Time') \
                    .bind_visibility_from(self.CastAPI.player)
    
                media_reset_icon = ui.icon('restore')
                media_reset_icon.tooltip('sync Reset')
                media_reset_icon.style("cursor: pointer")
                media_reset_icon.on('click', lambda: self.reset_sync())
                media_reset_icon.bind_visibility_from(self.CastAPI.player)
    
                await nice.sync_button(self.CastAPI, self.Media)
    
                self.CastAPI.slider_button_sync = ui.button('TSync', on_click=self.slider_sync, color='green') \
                    .tooltip('Sync Cast with Slider Time') \
                    .bind_visibility_from(self.CastAPI.player)
    
                media_sync_delay = ui.knob(1, min=1, max=59, step=1, show_value=True).classes('bg-gray')
                media_sync_delay.bind_value(self.Media, 'auto_sync_delay')
                media_sync_delay.tooltip('Interval in sec to auto sync')
                media_sync_delay.bind_visibility_from(self.CastAPI.player)
    
                ui.checkbox('Auto Sync') \
                    .bind_value(self.Media, 'auto_sync') \
                    .tooltip('Auto Sync Cast with Time every x sec (based on interval set)') \
                    .bind_visibility_from(self.CastAPI.player)
    
                ui.knob(1, min=-2000, max=2000, step=1, show_value=True).classes('bg-gray') \
                    .bind_value(self.Media, 'add_all_sync_delay') \
                    .tooltip('Add Delay in ms to all sync') \
                    .bind_visibility_from(self.CastAPI.player)
    
                ui.checkbox('Sync All') \
                    .bind_value(self.Media, 'all_sync') \
                    .tooltip('Sync All Casts with selected time') \
                    .bind_visibility_from(self.CastAPI.player)
    
            if str2bool(cfg_mgr.custom_config['gif_enabled']):
                with ui.row() as gif_buttons:
                    gif_buttons.classes('self-center')
                    gif_buttons.set_visibility(False)
    
                    if gif_buttons.visible:
                        gif_buttons.classes(add='animate__animated animate__flipOutX',
                                            remove='animate__animated animate__flipInX')
                        sync_buttons.classes(add='animate__animated animate__flipOutX',
                                             remove='animate__animated animate__flipInX')
    
                    else:
                        gif_buttons.classes(add='animate__animated animate__flipInX',
                                            remove='animate__animated animate__flipOutX')
                        sync_buttons.classes(add='animate__animated animate__flipInX',
                                             remove='animate__animated animate__flipOutX')
    
                    start_gif = ui.number('Start',value=0, min=0, max=self.CastAPI.video_frames, precision=0)
                    start_gif.bind_value(self.CastAPI,'current_frame')
                    end_gif = ui.number('End', value=self.CastAPI.video_frames, min=0, max=self.CastAPI.video_frames, precision=0)
    
                    gen_gif = ui.button(text='GIF',icon='image', on_click=create_gif)
                    gen_gif.tooltip('Create GIF')
                    gen_gif.bind_visibility_from(self.CastAPI.player)
    
                    if self.Media.wled:
                        send_gif = ui.button(text='WLED',icon='apps', on_click=gif_to_wled)
                        send_gif.tooltip('Upload GIF to WLED device')
                        send_gif.bind_visibility_from(self.CastAPI.player)
                        open_wled = ui.button('APP', icon='web', on_click=lambda: ui.navigate.to(f'http://{self.Media.host}', new_tab=True))
                        open_wled.tooltip('Open WLED Web Page')
                        open_wled.bind_visibility_from(self.CastAPI.player)
    
            with ui.row().classes('self-center'):
                show_player = ui.icon('switch_video', color='blue', size='xl')
                show_player.style("cursor: pointer")
                show_player.on('click', lambda: manage_visibility(True))
                show_player.tooltip("Show Video player")
                show_player.bind_visibility_from(self.CastAPI.player, backward=lambda v: not v)
    
                hide_player = ui.icon('disabled_visible', color='red', size='sm').classes('m-1')
                hide_player.style("cursor: pointer")
                hide_player.on('click', lambda: manage_visibility(False))
                hide_player.tooltip("Hide Video player")
                hide_player.bind_visibility_from(self.CastAPI.player)
    
                cast_number = ui.number(min=-1, max=9999, precision=0, placeholder='Repeat')
                cast_number.tooltip('Enter number of time you want to re-cast self.Media')
                cast_number.bind_value(self.Media, 'repeat')
                cast_number.bind_visibility_from(self.CastAPI.player)
    
                ui.icon('cast', size='md') \
                    .style("cursor: pointer") \
                    .on('click', lambda: self.player_cast(self.CastAPI.player.source)) \
                    .tooltip('Play/Cast Video') \
                    .bind_visibility_from(self.CastAPI.player)
    
                ui.icon('info', size='sd') \
                    .style("cursor: pointer") \
                    .on('click', lambda: nice.player_media_info(self.CastAPI.player.source)) \
                    .tooltip('self.Media Info') \
                    .bind_visibility_from(self.CastAPI.player)
    
                ui.icon('folder', color='orange', size='md').classes('m-4') \
                    .style("cursor: pointer") \
                    .on('click', lambda: player_set_file()) \
                    .tooltip('Select audio / video file') \
                    .bind_visibility_from(self.CastAPI.player)
    
                video_img_url = ui.input('Enter video/image Url / Path', placeholder='http://....') \
                    .bind_visibility_from(self.CastAPI.player)
                video_img_url.tooltip('Enter Url, select icon to download video/image, or stream video')
                video_img_url.on('focus', js_handler='''(event) => {const input = event.target;input.select();}''')
                video_stream_icon = ui.icon('published_with_changes', size='sm')
                video_stream_icon.style("cursor: pointer")
                video_stream_icon.tooltip("stream from Url")
                video_stream_icon.on('click', lambda: validate_player_url())
                video_stream_icon.bind_visibility_from(self.CastAPI.player)
                video_url_icon = ui.icon('file_download', size='sm')
                video_url_icon.style("cursor: pointer")
                video_url_icon.tooltip("Download video/image from Url")
                video_url_icon.on('click', lambda: player_set_url(video_img_url.value))
                video_url_icon.bind_visibility_from(self.CastAPI.player)
    
                # if yt_enabled is True display YT info icon
                if str2bool(cfg_mgr.custom_config['yt_enabled']):
                    video_url_info = ui.icon('info')
                    video_url_info.style("cursor: pointer")
                    video_url_info.tooltip("Youtube/Url information's, including formats etc ...")
                    video_url_info.on('click', lambda: nice.player_url_info(video_img_url.value))
                    video_url_info.bind_visibility_from(self.CastAPI.player)
    
                # Progress bar
                self.CastAPI.progress_bar = ui.linear_progress(value=0, show_value=False, size='8px')
    
            with ui.row(wrap=True).classes('w-full'):
                # if yt_enabled is True display YT search buttons
                if str2bool(cfg_mgr.custom_config['yt_enabled']):
                    # YT search
                    yt_icon = ui.chip('YT Search',
                                      icon='youtube_searched_for',
                                      color='indigo-3',
                                      on_click=lambda: self.youtube_search(video_img_url))
                    yt_icon.classes('fade')
                    yt_icon.bind_visibility_from(self.CastAPI.player)
                    yt_icon_2 = ui.chip('Clear YT Search',
                                      icon='clear',
                                      color='indigo-3',
                                      on_click=lambda: self.youtube_clear_search())
                    yt_icon_2.bind_visibility_from(self.CastAPI.player)
    
                # if gif_enabled is True display GIF buttons
                if str2bool(cfg_mgr.custom_config['gif_enabled']):
                    # YT search
                    gif_icon = ui.chip('GIF Menu',
                                      icon='image',
                                      color='indigo-2',
                                      on_click=open_gif)
                    gif_icon.classes('fade')
                    gif_icon.bind_visibility_from(self.CastAPI.player)
                    gif_icon_2 = ui.chip('GIF Close',
                                      icon='clear',
                                      color='indigo-2',
                                      on_click=close_gif)
                    gif_icon_2.bind_visibility_from(self.CastAPI.player)
    
