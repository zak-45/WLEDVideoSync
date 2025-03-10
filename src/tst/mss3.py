import cv2
import mss
import numpy as np

# Define the screen region to capture (adjust as needed)
monitor = {"top": 100, "left": 100, "width": 800, "height": 600}

with mss.mss() as sct:
    while True:
        # Capture screen frame
        frame = sct.grab(monitor)

        # Convert to numpy array (BGR format for OpenCV)
        img = np.array(frame)  # RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)  # Convert to BGR

        # Show the frame in OpenCV window
        cv2.imshow("Screen Capture", img)

        # Break loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

# Cleanup
cv2.destroyAllWindows()
