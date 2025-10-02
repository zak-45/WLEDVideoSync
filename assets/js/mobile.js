/**
 * @file mobile.js
 * @author zak-45
 * @date 15/08/2025
 * @version 1.0.0
 *
 * @description
 * This script turns a mobile device's browser into a wireless webcam for the WLEDVideoSync application.
 * It captures video from the phone's camera, establishes a secure WebSocket connection to the Python
 * server, and streams the video frames in real-time.
 *
 * @features
 * - **Camera Access**: Uses `navigator.mediaDevices.getUserMedia` to access the device's camera.
 * - **Camera Switching**: Allows toggling between the front ('user') and rear ('environment') cameras.
 * - **Robust Streaming**: Captures frames at a set interval, draws them to a canvas, encodes them as
 *   JPEG data URLs, and sends them over a WebSocket.
 * - **WebSocket Management**: Automatically establishes a secure WebSocket (`wss://`) connection and
 *   attempts to reconnect if the connection is lost.
 * - **Interactive UI**:
 *   - Displays the live video feed.
 *   - Provides a "Streaming..." status indicator that blinks during transmission.
 *   - Allows the user to pause and resume the stream by clicking the status indicator.
 *
 * @how-it-works
 * 1. **`startVideoStream()`**: The script's entry point. It requests camera access, trying the rear
 *    camera first and falling back to any available camera.
 * 2. **`setupWebSocket()`**: Once the video stream is active, this function initializes the WebSocket
 *    connection to the server's `/mobile` endpoint.
 * 3. **`startStreaming()`**: When the WebSocket connection is open, this function sets up an interval
 *    to repeatedly capture, encode, and send video frames.
 * 4. **Event Listeners**: Click handlers are attached to the "Switch Camera" button and the status
 *    indicator to control the stream and camera selection.
 */

const video = document.getElementById('video');
const statusIndicator = document.getElementById('status-indicator');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const switchCameraButton = document.getElementById('switch-camera-btn');
let socket;
let intervalId;
let currentStream;
let currentFacingMode = 'environment'; // Start with 'environment' (rear camera)

/**
 * Initializes and manages the secure WebSocket connection to the server for video streaming.
 * Automatically handles connection establishment, reconnection, and updates the UI status.
 *
 * Sets up a WebSocket to the server's `/mobile` endpoint using a secure protocol. Handles open, close,
 * and error events to manage streaming and UI feedback, and attempts reconnection if the connection drops.
 */
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

/**
 * Begins capturing video frames from the device's camera and streams them to the server.
 * Sets up a timed loop to encode and transmit each frame over the WebSocket connection.
 *
 * Creates a canvas to draw the current video frame, encodes it as a JPEG, and sends it to the server
 * at regular intervals while the WebSocket connection is open and the video is available.
 */
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

/**
 * Stops the transmission of video frames to the server and halts the streaming loop.
 * Clears the interval timer to pause frame capture and streaming until resumed.
 *
 * Cancels the active interval responsible for sending video frames and resets the streaming state.
 */
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

/**
 * Stops all active tracks in the current video stream to release camera resources.
 * Ensures the device's camera is properly turned off before switching or ending the stream.
 *
 * Iterates through all tracks in the current media stream and stops each one.
 */
function stopCurrentStream() {
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
    }
}

/**
 * Requests access to the device's camera and starts the video stream in the browser.
 * Attempts to use the specified camera facing mode, falling back to any available camera if needed.
 *
 * Tries a sequence of media constraints to obtain the desired camera stream, updates the video element
 * and UI, and initializes the WebSocket connection for streaming if necessary. Handles errors by displaying
 * a message and hiding the camera switch button.
 *
 * Args:
 *   facingMode (string): The preferred camera facing mode ('user' for front, 'environment' for rear).
 *
 * Returns:
 *   None
 */
function startVideoStream(facingMode) {
    stopCurrentStream();

    // Define a sequence of constraints to try, from most specific to most general
    const constraintSequence = [];
    if (facingMode) {
        constraintSequence.push({ video: { facingMode: { exact: facingMode } } });
        constraintSequence.push({ video: { facingMode: facingMode } });
    }
    constraintSequence.push({ video: true }); // Fallback to any camera

    let promiseChain = Promise.reject();

    constraintSequence.forEach(constraint => {
        promiseChain = promiseChain.catch(() => {
            console.log('Trying constraint:', JSON.stringify(constraint));
            return navigator.mediaDevices.getUserMedia(constraint);
        });
    });

    promiseChain.then(stream => {
        currentStream = stream;
        video.srcObject = stream;
        switchCameraButton.style.display = 'inline-block';

        // Update our state with the actual facing mode from the resulting stream
        const videoTrack = stream.getVideoTracks()[0];
        if (videoTrack) {
            const settings = videoTrack.getSettings();
            if (settings.facingMode) {
                console.log('Successfully started stream with facing mode:', settings.facingMode);
                currentFacingMode = settings.facingMode;
            }
        }

        // If WebSocket isn't set up yet, do it now.
        if (!socket || socket.readyState === WebSocket.CLOSED || socket.readyState === WebSocket.CLOSING) {
            setupWebSocket();
        }
    }).catch(error => {
        console.error('Could not access any camera:', error);
        const errorDiv = document.createElement('p');
        errorDiv.textContent = 'Error: Could not access webcam. Please check permissions.';
        errorDiv.style.color = 'red';
        video.parentElement.appendChild(errorDiv);
        switchCameraButton.style.display = 'none';
    });
}

switchCameraButton.addEventListener('click', () => {
    // Toggle between 'user' (front) and 'environment' (rear)
    const newFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
    startVideoStream(newFacingMode);
});

// Initial call to start video with the default camera (rear)
startVideoStream(currentFacingMode);
