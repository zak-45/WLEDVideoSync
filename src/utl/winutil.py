import pywinctl as pwc
import time
import json
from nicegui import run


def get_window_rect(title):
    """Find window position and size using pywinctl (cross-platform)."""

    try:
        if win := pwc.getWindowsWithTitle(title):
            win = win[0]  # Get the first matching window
            if win.isMinimized:
                win.restore()  # Restore if minimized

            win.activate()  # Bring window to front
            time.sleep(0.1)  # Wait for the window to be active

            return win.left, win.top, win.width, win.height

    except Exception as er:
        print(f"Not able to retrieve info for window name {title}. Error: {er}")

    return None


async def active_window():
    """ Provide active window title """

    return pwc.getActiveWindow().title


async def windows_titles():
    """ Provide a list of all window titles / hWnd by applications """

    try:

        class Point:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        class Size:
            def __init__(self, width, height):
                self.width = width
                self.height = height

        # Define a function to serialize custom objects
        def custom_serializer(obj):
            if isinstance(obj, Point):
                return {"x": obj.x, "y": obj.y}
            elif isinstance(obj, Size):
                return {"width": obj.width, "height": obj.height}
            raise TypeError(f"Type {type(obj)} not serializable")

        # Your dictionary
        data = await run.cpu_bound(pwc.getAllWindowsDict)
        # Convert dictionary to JSON
        all_windows = json.dumps(data, default=custom_serializer, ensure_ascii=False, sort_keys=True, indent=4)
        windows_by_app = json.loads(all_windows)

    except Exception as er:
        print(f"Error retrieving windows: {er}")
        return {}

    return windows_by_app


async def windows_names():
    windows = []
    try:
        win_dict = await windows_titles()
        for wins in win_dict:
            application = win_dict[wins]
            windows.extend(
                win_name for win_name in application['windows'] if win_name != ''
            )
        windows.sort()

    except Exception as er:
        print(f'Error to retrieve windows names : {er}')

    finally:
        return windows

