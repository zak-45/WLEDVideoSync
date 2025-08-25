"""
# a: zak-45
# d: 15/08/2025
# v: 1.0.0
#
#
This Python script creates a self-contained web application using `nicegui` to stream video from a mobile phone's camera
 to the main WLEDVideoSync application. It cleverly uses WebSockets for real-time, low-latency communication and a
 QR code for a seamless user experience, allowing a phone to act as a wireless webcam source.

### How It Works: A Step-by-Step Guide

1.  **Initialization**:
    *   The script is designed to be run as a separate process. When started, it initializes a `CASTDesktop` instance
    *   from the main application's library.
    *   Crucially, it sets this instance's video input to `'queue'` (`Desktop.viinput = 'queue'`).
    *   This tells the casting engine not to capture the screen, but to instead listen for image frames from
    *   a shared memory queue.
    *   It then calls `Desktop.cast()`, which starts the casting process in the background.
    *   This process creates the shared memory queue and waits for data to be placed into it.

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
        4.  Puts this NumPy frame into the shared memory queue that the `CASTDesktop` process is listening on.


### Summary

In essence, this file creates a bridge between a mobile phone's camera and the main application's casting engine.
The mobile browser does the work of capturing and sending frames, while this Python script acts as the receiver,
decoding the frames and feeding them into the WLEDVideoSync pipeline. This allows the mobile camera to be treated just
like any other video source, such as a desktop capture or a video file.


"""
import sys

from nicegui import ui, app
from PIL import Image
from io import BytesIO
from fastapi import WebSocket
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils as ImgUtils
from src.cst import desktop
from configmanager import cfg_mgr
import base64
import qrcode
import numpy as np

# Global placeholders to be set by the start_server function.
# This is a common pattern for web frameworks where route handlers are defined at the module level.
_stream_url = ''
_my_sl = None

@ui.page('/')
def index():
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
        ui.button('Shutdown', on_click=app.shutdown).classes('self-center')

# JavaScript to capture webcam frames and send via WebSocket
@ui.page('/stream')
def stream():
    ui.add_body_html('''
    <style>
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.2; }
            100% { opacity: 1; }
        }
        .blinking-dot {
            animation: blink 1.5s infinite;
        }
    </style>
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 90vh;">
        <h2>WLEDVideoSync - Mobile Webcam Stream (iOS/Android)</h2>
        <video id="video" autoplay playsinline width="320" height="240" style="border: 4px solid #ccc;"></video>
        <div id="status-indicator" style="display: none; align-items: center; margin-top: 10px; cursor: pointer;">
            <div id="status-dot" class="blinking-dot" style="width: 15px; height: 15px; background-color: #28a745; border-radius: 50%;"></div>
            <span id="status-text" style="margin-left: 8px; color: #28a745; font-weight: bold;">Streaming...</span>
        </div>
    </div>
    <script>
        const video = document.getElementById('video');
        const statusIndicator = document.getElementById('status-indicator');
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        let socket;
        let intervalId;

        function setupWebSocket() {
            // Use wss:// for secure connections, required for getUserMedia on most browsers
            socket = new WebSocket(`wss://${location.host}/mobile`);

            socket.onopen = () => {
                console.log('WebSocket connection established.');
                statusIndicator.style.display = 'flex';
                statusDot.classList.add('blinking-dot');
                statusText.textContent = 'Streaming...';
                startStreaming();
            };

            socket.onclose = (event) => {
                console.log('WebSocket connection closed. Attempting to reconnect in 2 seconds...', event.reason);
                statusIndicator.style.display = 'none';
                stopStreaming();
                setTimeout(setupWebSocket, 2000); // Try to reconnect after 2 seconds
            };

            socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                statusIndicator.style.display = 'none';
                // The onclose event will be triggered automatically, which handles reconnection.
            };
        }

        function startStreaming() {
            if (intervalId) clearInterval(intervalId); // Clear any existing interval

            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');

            intervalId = setInterval(() => {
                // Ensure video is ready and socket is open before sending
                if (video.videoWidth > 0 && socket && socket.readyState === WebSocket.OPEN) {
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    ctx.drawImage(video, 0, 0);
                    const dataURL = canvas.toDataURL('image/jpeg', 0.5); // Use a reasonable quality
                    socket.send(dataURL);
                }
            }, 100); // ~10 fps
        }

        function stopStreaming() {
            if (intervalId) clearInterval(intervalId);
            intervalId = null;
        }

        statusIndicator.addEventListener('click', () => {
            if (intervalId) { // If streaming, then pause
                stopStreaming();
                statusText.textContent = 'Paused';
                statusDot.classList.remove('blinking-dot');
            } else { // If paused, then resume
                startStreaming();
                statusText.textContent = 'Streaming...';
                statusDot.classList.add('blinking-dot');
            }
        });

        navigator.mediaDevices.getUserMedia({ video: true }).then(stream => {
            video.srcObject = stream;
            setupWebSocket(); // Start WebSocket connection after getting camera access
        }).catch(error => {
            console.error('Error accessing webcam:', error);
            const errorDiv = document.createElement('p');
            errorDiv.textContent = 'Error: Could not access webcam. Please check permissions.';
            errorDiv.style.color = 'red';
            video.parentElement.appendChild(errorDiv);
        });
    </script>
    ''')

# Handle WebSocket stream from browser
@app.websocket('/mobile')
async def websocket_mobile_endpoint(websocket: WebSocket):
    # retrieve shared memory and cast info
    sl, w, h = Utils.attach_to_manager_queue(f'{_my_sl.name}_q')

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
            data_url = await websocket.receive_text()
            header, encoded = data_url.split(',', 1)
            img_bytes = base64.b64decode(encoded)
            img = Image.open(BytesIO(img_bytes))

            # transform to numpy
            # send to shared memory
            frame = np.array(img)
            if all(item is not None for item in [sl, w, h]):
                ImgUtils.send_to_queue(frame, sl, w, h)

        except Exception as e:
            print(f'Received WebSocket error: {e}')
            break

# run app with SSL certificate
# SSL required to stream from remote browser (that's the case for mobile phone)
def start_server(shared_list, ip_address: str = '127.0.0.1'):
    """
    Configures and starts the mobile streaming server.

    This function sets the necessary global variables for the UI pages and WebSocket
    endpoint, then launches the secure NiceGUI web server.

    Args:
        shared_list: The shared list instance from the casting process.
        ip_address (str): The local IP address of the server.
    """
    global _stream_url, _my_sl

    # params from config
    port = int(cfg_mgr.app_config['ssl_port'])
    cert = cfg_mgr.app_config['ssl_cert_file']
    key = cfg_mgr.app_config['ssl_key_file']

    _stream_url = f'https://{ip_address}:{port}/stream'
    _my_sl = shared_list


    ui.run(
        title=f'WLEDVideoSync Mobile - {port}',
        favicon=cfg_mgr.app_root_path("favicon.ico"),
        port=port,
        show=True,
        ssl_certfile=cert,
        ssl_keyfile=key,
        reload=False
    )


if __name__ == "__main__":
    # args
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    wled = True if len(sys.argv) > 2 and sys.argv[2] == 'wled' else False
    # cast
    Desktop = desktop.CASTDesktop()
    Desktop.viinput = 'queue'
    Desktop.stopcast = False
    Desktop.host = host
    Desktop.wled = wled
    sl_instance = Desktop.cast()
    # local IP
    my_ip = Utils.get_local_ip_address()
    # run niceGui server
    start_server(sl_instance, my_ip)
