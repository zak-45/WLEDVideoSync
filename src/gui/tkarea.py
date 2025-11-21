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
    """ Retrieve coordinates from selected monitor region """

    coordinates = []
    screen_coordinates = []
    monitors = []
    pid_file = ''

    def __init__(self, tk_root, dk_monitor):
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
        self.root.wm_attributes('-alpha', 0.5)
        self.root.deiconify()

    def on_button_press(self, event):
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
        self.root.after(50, self.force_close)

    def force_close(self):
        """macOS-safe forced window close to ensure Tk mainloop exits."""
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

        try:
            self.root.quit()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

    @staticmethod
    def run(monitor_number: int = 0, pid_file: str = f'{os.getpid()}_file'):

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
            try:
                root.update_idletasks()
                root.update()
            except Exception:
                pass
            try:
                root.quit()
            except:
                pass
            try:
                root.destroy()
            except:
                pass
            tkarea_logger.debug('Root destroy requested')


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
