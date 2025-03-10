import cv2
import mss
import numpy as np

with mss.mss() as sct:
    # Get monitor dimensions for full-screen capture
    monitor = sct.monitors[1]  # [0] is the virtual screen, [1] is the primary monitor

    while True:
        # Capture full-screen
        frame = sct.grab(monitor)

        # Convert to NumPy array and format for OpenCV
        img = np.array(frame)  # RGB format
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)  # Convert to BGR for OpenCV

        # Display in OpenCV window
        cv2.imshow("Full Screen Capture", img)

        # Exit on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

# Cleanup
cv2.destroyAllWindows()
