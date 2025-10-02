
const video = document.getElementById('video');
const statusIndicator = document.getElementById('status-indicator');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const switchCameraButton = document.getElementById('switch-camera-btn');
let socket;
let intervalId;
let currentStream;
let currentFacingMode = 'environment'; // Start with 'environment' (rear camera)

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

function stopCurrentStream() {
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
    }
}

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
