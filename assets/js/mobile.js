document.addEventListener('DOMContentLoaded', () => {
     // --- DOM Elements ---
     const videoEl = document.getElementById('video');
     const imagePreviewEl = document.getElementById('image-preview');
     const statusIndicatorEl = document.getElementById('status-indicator');
     const statusTextEl = document.getElementById('status-text');
     const sourceInfoEl = document.getElementById('source-info');
     const fileInputEl = document.getElementById('file-input');
     const selectFileBtn = document.getElementById('select-file-btn');
     const cameraModeBtn = document.getElementById('camera-mode-btn');
     const screenCaptureBtn = document.getElementById('screen-capture-btn');
     const playFileBtn = document.getElementById('play-file-btn');
     const switchCameraBtn = document.getElementById('switch-camera-btn');

     // --- State Management ---
     const state = {
         ws: null,
         isStreaming: false,
         currentStream: null,
         facingMode: 'user', // 'user' for front, 'environment' for back
         source: null, // 'camera', 'screen', 'video', 'image'
         canvas: document.createElement('canvas'),
         ctx: null,
     };
     state.ctx = state.canvas.getContext('2d');

     // --- WebSocket Logic ---
     function connectWebSocket() {
         const protocol = window.location.protocol === 'https' ? 'wss' : 'wss';
         state.ws = new WebSocket(`${protocol}://${window.location.host}/ws-mobile`);

         state.ws.onopen = () => {
             console.log('WebSocket connection established');
             setStreamingState(true);
         };
         state.ws.onclose = () => {
             console.log('WebSocket connection closed. Reconnecting in 2s...');
             setStreamingState(false);
             setTimeout(connectWebSocket, 2000);
         };
         state.ws.onerror = (error) => console.error('WebSocket error:', error);
     }

     // --- Streaming Logic ---
     function setStreamingState(isStreaming) {
         state.isStreaming = isStreaming;
         statusTextEl.textContent = isStreaming ? 'Streaming...' : 'Paused';
         statusIndicatorEl.querySelector('.blinking-dot').style.animation = isStreaming ? 'blink 1.5s infinite' : 'none';
         statusIndicatorEl.querySelector('.blinking-dot').style.opacity = isStreaming ? 1 : 0.5;
         if (isStreaming) {
             streamFrame(); // Start the loop if we are now streaming
         }
     }

     function stopCurrentMedia() {
         if (state.currentStream) {
             state.currentStream.getTracks().forEach(track => track.stop());
             state.currentStream = null;
         }
         videoEl.pause();
         videoEl.src = '';
         videoEl.srcObject = null;
         URL.revokeObjectURL(imagePreviewEl.src);
         imagePreviewEl.src = '';
     }

     function streamFrame() {
         if (!state.isStreaming || !state.ws || state.ws.readyState !== WebSocket.OPEN) {
             state.isStreaming = false;
             return; // Stop the loop
         }

         let sourceElement = null;
         if (state.source === 'image' && imagePreviewEl.naturalWidth > 0) {
             sourceElement = imagePreviewEl;
             state.canvas.width = sourceElement.naturalWidth;
             state.canvas.height = sourceElement.naturalHeight;
         } else if (['camera', 'screen', 'video'].includes(state.source) && videoEl.videoWidth > 0) {
             sourceElement = videoEl;
             state.canvas.width = sourceElement.videoWidth;
             state.canvas.height = sourceElement.videoHeight;
         }

         if (sourceElement) {
             state.ctx.drawImage(sourceElement, 0, 0, state.canvas.width, state.canvas.height);
             state.canvas.toBlob(blob => {
                 if (blob && state.ws.readyState === WebSocket.OPEN) {
                     state.ws.send(blob);
                 }
             }, 'image/jpeg', 0.5); // Quality at 0.7 is a good balance
         }

         requestAnimationFrame(streamFrame); // Continue the loop
     }

     // --- Media Source Handlers ---
     async function setSource(sourceType, streamOrFile = null) {
         stopCurrentMedia();
         state.source = sourceType;
         statusIndicatorEl.style.display = 'flex';
         playFileBtn.style.display = 'none';
         switchCameraBtn.style.display = 'none';
         videoEl.style.display = 'none';
         imagePreviewEl.style.display = 'none';

         if (sourceType === 'camera' || sourceType === 'screen') {
             videoEl.style.display = 'block';
             videoEl.srcObject = streamOrFile;
             state.currentStream = streamOrFile;
             videoEl.play();
             sourceInfoEl.textContent = `Streaming from: ${sourceType === 'camera' ? (state.facingMode === 'user' ? 'Front Camera' : 'Back Camera') : 'Screen'}`;
             if (sourceType === 'camera') switchCameraBtn.style.display = 'block';
         } else if (sourceType === 'image') {
             imagePreviewEl.style.display = 'block';
             imagePreviewEl.src = URL.createObjectURL(streamOrFile);
             sourceInfoEl.textContent = `Streaming Image: ${streamOrFile.name}`;
         } else if (sourceType === 'video') {
             videoEl.style.display = 'block';
             videoEl.src = URL.createObjectURL(streamOrFile);
             videoEl.loop = true;
             videoEl.play();
             sourceInfoEl.textContent = `Streaming Video: ${streamOrFile.name}`;
         }
         setStreamingState(true);
     }

    async function startCamera(useFacingMode) {
         try {
             const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: useFacingMode } });
             state.facingMode = useFacingMode;
             setSource('camera', stream);
         } catch (err) {
             console.error("Error accessing camera:", err);
             alert("Could not access camera. Please ensure permissions are granted.");
         }
     }

    async function startScreenCapture() {
         if (!navigator.mediaDevices.getDisplayMedia) {
             return alert("Your browser does not support screen capture.");
         }
         try {
             const stream = await navigator.mediaDevices.getDisplayMedia({ video: { cursor: "always" }, audio: false });
             setSource('screen', stream);
         } catch (err) {
             console.error("Error capturing screen:", err);
             alert("Screen capture failed. Please ensure permissions are granted.");
         }
    }

    // --- Event Listeners ---
    statusIndicatorEl.addEventListener('click', () => setStreamingState(!state.isStreaming));
    selectFileBtn.addEventListener('click', () => fileInputEl.click());
    cameraModeBtn.addEventListener('click', () => startCamera(state.facingMode));
    screenCaptureBtn.addEventListener('click', startScreenCapture);
    switchCameraBtn.addEventListener('click', () => {
         const newMode = state.facingMode === 'user' ? 'environment' : 'user';
         startCamera(newMode);
    });

    fileInputEl.addEventListener('change', (event) => {
         const file = event.target.files[0];
         if (!file) return;

         if (file.type.startsWith('image/')) {
             setSource('image', file);
         } else if (file.type.startsWith('video/')) {
             if (videoEl.canPlayType(file.type)) {
                 setSource('video', file);
             } else {
                 alert(`Error: The video format (${file.type}) is not supported by your browser.`);
             }
         } else {
             alert('Unsupported file type.');
         }
         fileInputEl.value = ''; // Reset input to allow selecting the same file again
    });
    // --- Initial Setup ---
    connectWebSocket();
    startCamera(state.facingMode); // Start with front camera by default
});