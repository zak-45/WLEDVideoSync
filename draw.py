import tkinter as tk
from screeninfo import get_monitors


class ScreenAreaSelection:
    """ Retrieve coordinate from selected desktop region """
    def __init__(self, root, monitor):
        self.root = root
        self.monitor = monitor

        # Set the geometry to match the selected monitor
        self.root.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.attributes('-alpha', 0.5)  # Set window transparency
        self.root.configure(bg='black')

        self.canvas = tk.Canvas(root, cursor="cross", bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

    def on_button_press(self, event):
        # Save mouse drag start position
        self.start_x = event.x
        self.start_y = event.y
        # Create rectangle if not yet exist
        if not self.rect:
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='blue', width=4)

    def on_mouse_drag(self, event):
        curX, curY = (event.x, event.y)
        # Expand rectangle as you drag the mouse
        self.canvas.coords(self.rect, self.start_x, self.start_y, curX, curY)

    def on_button_release(self, event):
        # Get the coordinates of the rectangle
        coords = self.canvas.coords(self.rect)
        print(f"Rectangle coordinates (relative to window): {coords}")

        # Adjust coordinates to be relative to the screen
        screen_coords = [
            coords[0] + self.monitor.x,
            coords[1] + self.monitor.y,
            coords[2] + self.monitor.x,
            coords[3] + self.monitor.y,
        ]
        print(f"Rectangle coordinates (relative to screen): {screen_coords}")


if __name__ == "__main__":
    # Get monitor information
    monitors = get_monitors()

    for i, m in enumerate(monitors):
        print(f"Monitor {i}: {m}")

    # Change the monitor index as needed
    monitor_index = 1  # Change this to the desired monitor index (0 for first monitor, 1 for second, etc.)

    if monitor_index >= len(monitors):
        print(f"Monitor index {monitor_index} is out of range. Using the first monitor instead.")
        monitor_index = 0

    monitor = monitors[monitor_index]

    # Create a Tkinter window on the selected monitor
    root = tk.Tk()
    root.title("Draw a Rectangle on Monitor")
    app = ScreenAreaSelection(root, monitor)
    root.mainloop()
