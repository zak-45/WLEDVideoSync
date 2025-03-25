from nicegui import ui


async def player_duration():
    """
    Return current duration time from the Player
    Set slider max value to video duration
    """
    # await ui.context.client.connected()
    current_duration = await ui.run_javascript("document.querySelector('video').duration", timeout=2)
    ui.notify(f'Video duration:{current_duration}')

async def get_player_time():
    """
    Retrieve current play time from the Player
    Set player time for Cast to Sync & current frame number
    """
    # await ui.context.client.connected()
    current_time = float(await ui.run_javascript("document.querySelector('video').currentTime", timeout=2))
    ui.notify(f'Video time : {current_time}')

@ui.page('/')
async def player():
    # test_video = ui.video('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4')
    test_video = ui.video(r"C:\Users\zak-4\Videos\BigBuckBunny.webm")
    test_video.on('timeupdate', lambda: get_player_time())
    test_video.on('ended', lambda _: ui.notify('Video playback completed.'))
    test_video.on('durationchange', lambda: player_duration())

ui.run(fastapi_docs=True)