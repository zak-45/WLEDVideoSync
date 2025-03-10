import cv2
import mss
import numpy as np
import pygetwindow as gw
import win32gui
import win32con

# Specify the window title (case-sensitive, match exact title)
WINDOW_TITLE = "Notepad"  # Change to your desired window


def get_window_rect(title):
    """Find the position and size of a window by title."""
    try:
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            win32gui.SetForegroundWindow(hwnd)  # Bring window to front
            rect = win32gui.GetWindowRect(hwnd)  # Get window bounds
            return hwnd, rect  # (left, top, right, bottom)
    except Exception as e:
        print(f"Error: {e}")
    return None, None


with mss.mss() as sct:
    hwnd, rect = get_window_rect(WINDOW_TITLE)

    if rect:
        left, top, right, bottom = rect
        width, height = right - left, bottom - top
        monitor = {"top": top, "left": left, "width": width, "height": height}

        while True:
            # Capture only the window area
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
