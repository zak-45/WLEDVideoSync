from nicegui import ui
import sys
import multiprocessing
import threading
import time

class ConsoleCapture:
    """Captures and displays console output in a NiceGUI UI.

    Redirects stdout and stderr to a queue, which is then displayed
    in an ui.log element.  Provides options for UI customization and restoring
    the original console output streams.
    """
    def __init__(self, show_console=False, text_color='text-white', bg_color='bg-black'):
        """Initialize the ConsoleCapture.

        Sets up console capturing by redirecting stdout and stderr, initializing the UI
        if requested, and starting a background thread to process captured output.
        """
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.text_color = text_color
        self.bg_color = bg_color
        if show_console:
            self.setup_ui()
        else:
            self.log_ui = None
        self.log_queue = multiprocessing.Queue()

        sys.stdout = self
        sys.stderr = self

        # Start a background thread to read from the queue
        self.running = True
        threading.Thread(target=self.read_queue, daemon=True).start()

    def setup_ui(self):
        """Set up the UI for the console output.

        Creates and configures an ui.log element to display captured console output,
        applying specified styling classes.
        """
        self.log_ui = ui.log()
        self.log_ui.classes(f'console-output w-full h-30 {self.bg_color} {self.text_color}')

    def write(self, text):
        """Override sys.stdout and sys.stderr to send output to the queue and original streams."""
        if text.strip():
            self.log_queue.put(text.strip())  # Send to the queue
            # Write to the original stdout or stderr
            if "Error" in text:
                self.original_stderr.write(text)
            else:
                self.original_stdout.write(text)

    def flush(self):
        """Flush method for compatibility."""
        pass

    def restore(self):
        """Restore original stdout and stderr."""
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self.running = False

    def read_queue(self):
        """Continuously read from the queue and update the UI log."""
        while self.running:
            try:
                while not self.log_queue.empty():
                    log_message = self.log_queue.get()
                    if self.log_ui is not None:
                        self.log_ui.push(log_message)
            except Exception as e:
                self.original_stderr.write(f"Queue reading error: {e}\n")
            time.sleep(0.1)  # Prevent busy waiting



if __name__ in {"__main__", "__mp_main__"}:
    # NiceGUI app
    @ui.page('/')
    async def main_page():

        capture = ConsoleCapture(show_console=False)

        with ui.column():
            ui.button('Print Message', on_click=lambda: print('Hello from stdout!'))
            ui.button('Raise Exception', on_click=lambda: 1 / 0)
            ui.button('Send Custom Log', on_click=lambda: capture.log_queue.put("[INFO] Custom log message"))
            ui.button('Restore Console', on_click=capture.restore)

        capture.setup_ui()

    ui.run(reload=False)

