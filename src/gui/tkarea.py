"""
a: zak-45
d: 01/05/2025
v: 1.0.0

overview
    This code provides a graphical user interface (GUI) for selecting a rectangular area on a specific monitor.
    It uses the tkinter library to create a transparent window overlayed on the chosen monitor.
    The user can click and drag to define a rectangle, and the coordinates of the selected area are then stored
    in the class variables coordinates and screen_coordinates.

"""

import os
import shelve
import tkinter as tk

from screeninfo import get_monitors

from configmanager import cfg_mgr, LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.tkarea')
tkarea_logger = logger_manager.logger

class ScreenAreaSelection:
    """
    Provides a GUI for selecting a rectangular area on a specific monitor using tkinter.
    Allows users to click and drag to define a rectangle, storing the selected coordinates for later use.

    Attributes:
        coordinates (list): Stores the coordinates of the selected area.
        screen_coordinates (list): Stores the screen coordinates of the selected area.
        monitors (list): List of detected monitors.
        pid_file (str): Path to the file used for saving coordinates.

    Args:
        tk_root: The tkinter root window.
        dk_monitor: The monitor object on which to select the area.
    """

    coordinates = []
    screen_coordinates = []
    monitors = []
    pid_file = ''

    def __init__(self, tk_root, dk_monitor):
        """
        Initializes the area selection window and sets up the canvas for user interaction.
        Configures the window to match the selected monitor and prepares event bindings for area selection.

        Args:
            tk_root: The tkinter root window.
            dk_monitor: The monitor object on which to select the area.
        """
        self.root = tk_root
        self.monitor = dk_monitor

        # Set the geometry to match the selected monitor
        self.root.geometry(
            f"{self.monitor.width}x{self.monitor.height}+{self.monitor.x}+{self.monitor.y}"
        )
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.withdraw()  # Hide window initially to avoid flicker

        self.canvas = tk.Canvas(
            self.root, cursor="cross", highlightthickness=0, bg='gray'
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Apply transparency after short delay
        self.root.after(100, self.apply_transparency)

    def apply_transparency(self):
        """
        Makes the selection window semi-transparent and displays it to the user.
        This helps users see the underlying screen while selecting an area.
        """
        self.root.wm_attributes('-alpha', 0.5)
        self.root.deiconify()

    def on_button_press(self, event):
        """
        Handles the mouse button press event to start area selection.
        Records the starting coordinates and initializes the selection rectangle.

        Args:
            event: The tkinter event object containing mouse position data.
        """
        tkarea_logger.debug(f'Tkarea event : {event}')

        self.start_x = event.x_root
        self.start_y = event.y_root

        if not self.rect:
            self.rect = self.canvas.create_rectangle(
                self.start_x - self.monitor.x,
                self.start_y - self.monitor.y,
                self.start_x - self.monitor.x + 1,
                self.start_y - self.monitor.y + 1,
                outline='blue',
                width=4
            )

    def on_mouse_drag(self, event):
        """
        Handles the mouse drag event to update the selection rectangle.
        Dynamically resizes the rectangle as the user drags the mouse.

        Args:
            event: The tkinter event object containing mouse position data.
        """
        tkarea_logger.debug(f'Tkarea event : {event}')

        cur_x, cur_y = event.x_root, event.y_root

        self.canvas.coords(
            self.rect,
            self.start_x - self.monitor.x,
            self.start_y - self.monitor.y,
            cur_x - self.monitor.x,
            cur_y - self.monitor.y
        )

    def on_button_release(self, event):
        """
        Handles the mouse button release event to finalize area selection.
        Stores the selected coordinates and saves them to a file for later retrieval.

        Args:
            event: The tkinter event object containing mouse position data.
        """
        tkarea_logger.debug(f'Tkarea event : {event}')

        end_x, end_y = event.x_root, event.y_root

        screen_coordinates = [
            min(self.start_x, end_x),
            min(self.start_y, end_y),
            max(self.start_x, end_x),
            max(self.start_y, end_y),
        ]

        ScreenAreaSelection.screen_coordinates = screen_coordinates

        pid_tmp_file = ScreenAreaSelection.pid_file
        try:
            with shelve.open(pid_tmp_file, 'c') as process_file:
                process_file["sc_area"] = screen_coordinates
                tkarea_logger.debug(
                    f"Set Coordinates {screen_coordinates} to shelve:{pid_tmp_file}"
                )
        except Exception as er:
            tkarea_logger.error(
                f"Error saving screen coordinates to shelve: {er}"
            )

        # *** macOS FIX: force event flush then quit/destroy ***
        self.root.after(50, ScreenAreaSelection.force_close, self.root)

    @staticmethod
    def force_close(obj):
        """Linux/macOS-safe forced window close to ensure Tk mainloop exits.
                Safely closes and destroys a tkinter window or widget.
        Attempts to update, quit, and destroy the object, ignoring any exceptions that occur.

        Args:
            obj: The tkinter window or widget to be closed.
        """
        try:
            obj.update_idletasks()
            obj.update()
        except Exception:
            pass

        try:
            obj.quit()
        except Exception:
            pass

        try:
            obj.destroy()
        except Exception:
            pass

    @staticmethod
    def run(monitor_number: int = 0, pid_file: str = f'{os.getpid()}_file'):
        """
        Launches the area selection GUI on the specified monitor and saves the selected coordinates.
        Initializes the tkinter main loop and handles monitor selection, window setup, and cleanup.

        Args:
            monitor_number (int): The index of the monitor to use for area selection.
            pid_file (str): The file path for saving the selected coordinates.
        """
        monitors = get_monitors()
        ScreenAreaSelection.monitors = monitors
        ScreenAreaSelection.pid_file = pid_file

        monitor_index = monitor_number
        if monitor_index >= len(monitors):
            tkarea_logger.warning(
                f"Monitor index {monitor_index} is out of range. Using 0."
            )
            monitor_index = 0

        monitor = monitors[monitor_index]

        root = tk.Tk()
        root.title("Area Selection on Monitor")
        ScreenAreaSelection(root, monitor)

        try:
            tkarea_logger.debug(f'Main Loop entering ...: {os.getpid()}')
            root.mainloop()
            tkarea_logger.debug('Main Loop finished')
            tkarea_logger.debug(f'Monitors infos: {ScreenAreaSelection.monitors}')
            tkarea_logger.debug(
                f'Area screen Coordinates: {ScreenAreaSelection.screen_coordinates}'
            )
        except Exception as er:
            tkarea_logger.error(f'Tkinter mainloop closed by exception: {er}')
        finally:
            # Final cleanup for safety
            ScreenAreaSelection.force_close(root)
            tkarea_logger.debug(f'Root destroy requested : {os.getpid()}')


if __name__ == '__main__':

    p_file = cfg_mgr.app_root_path(f'tmp/sc_{os.getpid()}_file')
    ScreenAreaSelection.run(monitor_number=1, pid_file=p_file)
    print(f'Coordinates from Tk : {str(ScreenAreaSelection.screen_coordinates)}')
    print(f'Monitors from Tk : {str(ScreenAreaSelection.monitors)}')
    print(f'Selected monitor : {str(ScreenAreaSelection.monitors[1])}')

    try:
        with shelve.open(p_file, 'r') as proc_file:
            if saved_screen_coordinates := proc_file.get("sc_area"):
                print(f'Get Coordinates from shelve : {saved_screen_coordinates}')
    except Exception as e:
        tkarea_logger.error(f"Error loading screen coordinates: {e}")
