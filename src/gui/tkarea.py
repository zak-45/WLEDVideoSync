"""
a: zak-45
d: 01/05/2025
v: 1.0.0.0

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

from configmanager import LoggerManager, PLATFORM

logger_manager = LoggerManager(logger_name='WLEDLogger.tkarea')
tkarea_logger = logger_manager.logger

class ScreenAreaSelection:
    """ Retrieve coordinates from selected monitor region

    The ScreenAreaSelection class initializes a tkinter window positioned over the specified monitor.
    It uses a canvas to draw a rectangle based on user mouse input.
    The on_button_press, on_mouse_drag, and on_button_release methods handle the mouse events to capture the selection.
    The run method sets up the tkinter environment and creates an instance of ScreenAreaSelection.
    The selected area's coordinates, relative to both the window and the entire screen, are stored in static class variables.
    """

    coordinates = []
    screen_coordinates = []
    monitors = []
    pid_file = ''

    def __init__(self, tk_root, dk_monitor):
        self.root = tk_root
        self.monitor = dk_monitor

        # Set the geometry to match the selected monitor
        self.root.geometry(f"{self.monitor.width}x{self.monitor.height}+{self.monitor.x}+{self.monitor.y}")
        self.root.overrideredirect(True)  # Remove window decorations

        self.root.withdraw()  # Hide the window initially to avoid flicker

        self.canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Apply transparency and show window after short delay
        self.root.after(100, self.apply_transparency)

    def apply_transparency(self):
        self.root.wm_attributes('-alpha', 0.5)  # Set window transparency
        self.root.deiconify()  # Show the window

    def on_button_press(self, event):
        # Save mouse drag start position
        self.start_x = event.x
        self.start_y = event.y
        # Create rectangle if not yet exist
        if not self.rect:
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='blue', width=4)

    def on_mouse_drag(self, event):
        cur_x, cur_y = (event.x, event.y)
        # Expand rectangle as you drag the mouse
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        # Get the coordinates of the rectangle
        # y,x,w,h
        coordinates = self.canvas.coords(self.rect)
        ScreenAreaSelection.coordinates = coordinates

        tkarea_logger.debug(event)

        # Adjust coordinates to be relative to the screen
        screen_coordinates = [
            coordinates[0] + self.monitor.x,
            coordinates[1] + self.monitor.y,
            coordinates[2] + self.monitor.x,
            coordinates[3] + self.monitor.y,
        ]

        ScreenAreaSelection.screen_coordinates = screen_coordinates

        if PLATFORM == 'darwin':
            pid_tmp_file = ScreenAreaSelection.pid_file
            try:
                with shelve.open(pid_tmp_file, 'c') as process_file:
                    process_file["sc_area"] = ScreenAreaSelection.screen_coordinates
            except Exception as er:
                tkarea_logger.error(f"Error saving screen coordinates to shelve: {er}")

        self.root.destroy()

    @staticmethod
    def run(monitor_number: int = 0, pid_file: str = str(os.getpid())):
        """
        Initiate tk-inter
        param : monitor number to draw selection
                pid_file , shelve file name
        """
        # get all monitors info
        monitors = get_monitors()
        ScreenAreaSelection.monitors = monitors
        ScreenAreaSelection.pid_file = pid_file

        # Change the monitor index as needed
        monitor_index = monitor_number  # Change this to the desired monitor index (0 for first , 1 for second, etc.)
        if monitor_index >= len(monitors):
            tkarea_logger.warning(f"Monitor index {monitor_index} is out of range. Using the first monitor instead.")
            monitor_index = 0
        # monitor obj
        monitor = monitors[monitor_index]
        #
        root = tk.Tk()
        root.title("Area Selection on Monitor")
        ScreenAreaSelection(root, monitor)
        root.mainloop()


if __name__ == '__main__':

    ScreenAreaSelection.run(monitor_number=1)
    print(ScreenAreaSelection.screen_coordinates)
    if PLATFORM == 'darwin':
        # Read saved screen coordinates from shelve file
        try:
            with shelve.open(str(os.getpid()), 'r') as proc_file:
                if saved_screen_coordinates := proc_file.get("sc_area"):
                    print(f'for darwin : {saved_screen_coordinates}')
        except Exception as e:
            tkarea_logger.error(f"Error loading screen coordinates from shelve: {e}")
