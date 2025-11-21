"""
# a: zak-45
# d: 15/08/2025
# v: 1.0.0
#
#
This Python script creates a self-contained web application using `nicegui` to stream video from a mobile phone's camera
 to the main WLEDVideoSync application. It cleverly uses WebSockets for real-time, low-latency communication and a
 QR code for a seamless user experience, allowing a phone to act as a wireless webcam/Media Server source.

### How It Works: A Step-by-Step Guide

1.  **Initialization**:
    *   The script is designed to be run as a separate process. When started, it initializes a `CASTDesktop` instance
    *   from the main application's library.
    *   Crucially, it sets this instance's video input to `'SharedList'` (`Desktop.viinput = 'SharedList'`).
    *   This tells the casting engine not to capture the screen, but to instead listen for image frames from
    *   a shared memory List.
    *   It then calls `Desktop.cast()`, which starts the casting process in the background.
    *   This process creates the shared memory List and waits for data to be placed into it.

2.  **The Web Server**:
    *   The script starts a `nicegui` web server using a secure HTTPS connection (SSL/TLS).
    *   This is a mandatory requirement for modern browsers to grant access to a device's camera.
    *   The server hosts two main pages.

3.  **The Landing Page (`@ui.page('/')`)**:
    *   This is the entry point for the user.
    *   It generates and displays a QR code that contains the URL to the stream page (`https://<server_ip>:4443/stream`).
    *   A user on a computer can access this page and then simply scan the QR code with their mobile phone to connect,
    *   eliminating the need to type a complex URL.

4.  **The Stream Page (`@ui.page('/stream')`)**:
    *   This page is loaded on the mobile device. It contains client-side JavaScript that performs the following actions:
        *   **Camera Access**: It requests permission to use the phone's camera via the browser's
        *   `navigator.mediaDevices.getUserMedia` API.
        *   **WebSocket Connection**: It establishes a secure WebSocket (`wss://`) connection to the server's `/mobile`
        *   endpoint. This connection is persistent and allows for two-way communication. It also includes logic to
        *   handle automatically reconnect if the connection is lost.
        *   **Streaming**: It sets up an interval (running approximately 10 times per second). In each interval, it:
            1.  Captures the current frame from the video feed.
            2.  Draws it onto a hidden HTML `<canvas>`.
            3.  Encodes the canvas image as a Base64 string (in JPEG format).
            4.  Sends this string over the WebSocket to the Python server.
        *   **UI**: It displays the live camera feed and a blinking "Streaming..." indicator, which the user can tap to
        *   pause or resume the stream.

5.  **The WebSocket Endpoint (`@app.websocket('/mobile')`)**:
    *   This is the server-side component that handles the data coming from the mobile browser.
    *   It accepts the WebSocket connection.
    *   It enters a loop, continuously waiting to receive text data (the Base64 image string) from the client.
    *   For each message received, it:
        1.  Decodes the Base64 string back into image bytes.
        2.  Uses the Pillow (`PIL`) library to open these bytes as an image.
        3.  Converts the image into a NumPy array, a standard format for video processing in Python.
        4.  Puts this NumPy frame into the shared memory List that the `CASTDesktop` process is attached on.


### Summary

In essence, this file creates a bridge between a mobile phone's camera/media and the main application's casting engine.
The mobile browser does the work of capturing and sending frames, while this Python script acts as the receiver,
decoding the frames and feeding them into the WLEDVideoSync pipeline. This allows the mobile camera to be treated just
like any other video source, such as a desktop capture or a video file.


"""
from nicegui import ui, app
from PIL import Image
from io import BytesIO
from fastapi import WebSocket
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils as ImgUtils
from src.cst import desktop
from src.gui.niceutils import apply_custom
from configmanager import cfg_mgr
import base64
import qrcode
import numpy as np

# Global placeholders to be set by the start_server function.
# This is a common pattern for web frameworks where route handlers are defined at the module level.
_stream_url = ''
_my_thread = None
_sl_ip = None
_sl_port = None

@ui.page('/')
async def mobile_main_page():
    """
    Displays the landing page with a QR code for joining the WLEDVideoSync stream.

    This function generates a QR code containing the stream URL and presents it along with
    a link and shutdown button for user interaction.
    """

    await apply_custom()

    with ui.header(bordered=True, elevated=True).classes('items-center justify-between'):
        ui.label('Mobile Webcam / Media Stream').classes('text-2xl font-bold')
        power = ui.button(icon='power_settings_new', on_click=app.shutdown).classes('self-center')
        power.tooltip('Shutdown app')

    with ui.column().classes('self-center'):
        # Generate QR code as image
        qr = qrcode.make(_stream_url)
        qr_buf = BytesIO()
        qr.save(qr_buf, format='PNG')
        qr_b64 = base64.b64encode(qr_buf.getvalue()).decode()
        ui.label('📱 Scan to join WLEDVideoSync stream:').classes('self-center')
        ui.image(f'data:image/png;base64,{qr_b64}').style('width: 100px; height: 100px; border: 1px solid #ccc;') \
            .classes('self-center')
        ui.link('Open stream', _stream_url, new_tab=True).classes('self-center')


@ui.page('/stream')
async def stream():
    """
    Renders the mobile streaming page for capturing and transmitting video from a phone's camera.

    This function injects the necessary HTML, CSS, and JavaScript to enable live video capture,
    camera switching, and real-time streaming to the server via WebSocket.
    """

    await apply_custom()

    # Load external CSS and JS files for a cleaner structure
    ui.add_head_html('<link rel="stylesheet" href="/assets/css/mobile.css">')

    # Read the HTML content from the external file
    with open(cfg_mgr.app_root_path('assets/html/mobile.html'), 'r') as f:
        ui.add_body_html(f.read())

    ui.add_body_html('<script src="/assets/js/mobile.js"></script>')

@app.websocket('/ws-mobile')
async def websocket_mobile_endpoint(websocket: WebSocket):
    """
    Handles incoming WebSocket connections from mobile devices streaming video frames.

    This function receives base64-encoded image frames from the client, decodes and converts them
    to NumPy arrays, and forwards them to the shared memory queue for processing by the casting engine.
    SL name is thread name + _q for shared memory SL on which we put the frame + time.time
    """
    # retrieve shared memory to write frame and receive back name and cast info (w x h)
    sl_name, w, h = Utils.attach_to_manager_list(f'{_my_thread}_q', _sl_ip, _sl_port)

    # accept connection from mobile
    try:
        await websocket.accept()
    except Exception as e:
        print(f'WebSocket accept error: {e}')
        return

    # loop
    while True:

        # receive image from browser
        try:
            # Receive raw binary data (JPEG bytes) instead of base64 text
            jpeg_bytes = await websocket.receive_bytes()
            img = Image.open(BytesIO(jpeg_bytes))

            # transform to numpy
            # write to shared memory
            frame = np.array(img)
            if all(item is not None for item in [sl_name, w, h]):
                ImgUtils.update_sl_with_frame(frame, sl_name, w, h)

        except Exception as e:
            print(f'Received WebSocket error: {e}')
            break


# run app with SSL certificate
# SSL required to stream from remote browser (that's the case for mobile phone)
def start_server(thread_name, ip_address:str = '127.0.0.1', dark:bool = False, mgr_sl_ip:str = '127.0.0.1', mgr_sl_port:int = 50000):
    """
    Configures and starts the mobile streaming server.

    This function sets the necessary global variables for the UI pages and WebSocket
    endpoint, then launches the secure NiceGUI web server.

    Args:
        thread_name: The shared list thread name, used to identify from the casting process.
        ip_address (str): The local IP address of the server.
        dark (bool): Whether to use dark mode.
        mgr_sl_ip: SL Manager IP Address
        mgr_sl_port: SL Manager port Number
    """
    global _stream_url, _my_thread, _sl_ip, _sl_port

    # params from config
    ssl_port = int(cfg_mgr.app_config['ssl_port'])
    cert = cfg_mgr.app_config['ssl_cert_file']
    key = cfg_mgr.app_config['ssl_key_file']

    _stream_url = f'https://{ip_address}:{ssl_port}/stream'
    _my_thread = thread_name
    _sl_ip = mgr_sl_ip
    _sl_port = mgr_sl_port

    ui.run(
        root=mobile_main_page,
        title=f'WLEDVideoSync Mobile - {ssl_port}',
        favicon=cfg_mgr.app_root_path("favicon.ico"),
        host=ip_address,
        port=ssl_port,
        show=True,
        ssl_certfile=cert,
        ssl_keyfile=key,
        reload=False,
        dark=dark
    )

# Example running mobile server
if __name__ == "__main__":
    from nicegui import native
    from src.utl.sharedlistmanager import SharedListManager

    app.add_static_files('/assets', cfg_mgr.app_root_path('assets'))

    # cast settings
    Desktop = desktop.CASTDesktop()
    Desktop.viinput = 'SharedList'
    Desktop.stopcast = False
    Desktop.preview = True

    # local IP
    my_ip = Utils.get_local_ip_address()

    # find a free port
    sl_port = native.find_open_port(start_port=8800)
    # set to localhost
    sl_ip = '127.0.0.1'

    # define shared list manager we will use to access SL (not using the default one)
    sl_manager = SharedListManager(sl_ip_address=sl_ip, sl_port=sl_port)
    sl_manager.start()

    # set it in Desktop
    Desktop.sl_manager = sl_manager

    # as viinput = SharedList, this will create a ShareAble List {t_name}_q waiting for frames to be placed
    sl_instance = Desktop.cast()

    # run niceGui server
    start_server(sl_instance.name, my_ip,True, sl_ip, sl_port)
