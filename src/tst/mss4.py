import cv2
import mss
import numpy as np
import pywinctl
import time


def list_all_windows():
    """List all open window titles."""
    windows = pywinctl.getAllWindows()
    print("\n[ Available Windows ]")
    for win in windows:
        print(f"- {win.title}")
    print("\n")


def get_window_rect(title):
    """Find window position and size using pywinctl (cross-platform)."""
    try:
        win = pywinctl.getWindowsWithTitle(title)
        if win:
            win = win[0]  # Get the first matching window
            if win.isMinimized:
                win.restore()  # Restore if minimized

            win.activate()  # Bring window to front
            time.sleep(0.1)  # Wait for the window to be active

            return win.left, win.top, win.width, win.height
    except Exception as e:
        print(f"Error: {e}")
    return None


# List available windows before asking for input
list_all_windows()
WINDOW_TITLE = input("Enter the window title to capture: ")

with mss.mss() as sct:
    rect = get_window_rect(WINDOW_TITLE)

    if rect:
        left, top, width, height = rect
        monitor = {"top": top, "left": left, "width": width, "height": height}

        while True:
            # Capture the window area
            frame = sct.grab(monitor)

            # Convert to NumPy array for OpenCV
            img = np.array(frame)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            # Display in OpenCV
            cv2.imshow(WINDOW_TITLE, img)

            # Exit on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    else:
        print(f"Window '{WINDOW_TITLE}' not found.")

# Cleanup
cv2.destroyAllWindows()
