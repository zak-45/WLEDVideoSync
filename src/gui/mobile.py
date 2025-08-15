from nicegui import ui, app
from PIL import Image
from io import BytesIO
from fastapi import WebSocket
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils as ImgUtils
from src.cst import desktop
import base64
import qrcode
import numpy as np

# instantiate
Desktop = desktop.CASTDesktop()
# params
Desktop.stopcast = False
Desktop.host = '192.168.1.125'
Desktop.wled = False
Desktop.viinput = 'queue'
cert_file = r'C:\Users\zak-4\PycharmProjects\WLEDVideoSync\xtra\cert\cert.pem'
key_file = r'C:\Users\zak-4\PycharmProjects\WLEDVideoSync\xtra\cert\key.pem'
stream_url = 'https://192.168.1.32:4443/stream'

@ui.page('/')
def index():
    with ui.column().classes('self-center'):
        # Generate QR code as image
        qr = qrcode.make(stream_url)
        qr_buf = BytesIO()
        qr.save(qr_buf, format='PNG')
        qr_b64 = base64.b64encode(qr_buf.getvalue()).decode()
        ui.label('📱 Scan to join stream:').classes('self-center')
        ui.image(f'data:image/png;base64,{qr_b64}').style('width: 100px; height: 100px; border: 1px solid #ccc;') \
            .classes('self-center')
        ui.link('Open stream', stream_url, new_tab=True).classes('self-center')

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
    sl, w, h = Utils.attach_to_manager_queue(f'{my_sl.name}_q')

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
            print(f'Received WebSocket/Sl error: {e}')
            break

# run app with SSL certificate
# SSL required to stream from remote browser (that's the case for mobile phone)
def main():
    ui.run(
        port=4443,
        ssl_certfile=cert_file,
        ssl_keyfile=key_file,
        reload=False
    )

if __name__ == "__main__":
    # init cast
    my_sl = Desktop.cast()
    # run app
    main()
