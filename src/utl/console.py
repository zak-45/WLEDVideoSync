from nicegui import ui
from src.utl.utils import CASTUtils as Utils
import sys
import threading
from queue import Empty

# mp is required
Process, Queue = Utils.mp_setup()

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
        self.log_queue = Queue()

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
            if "Error" in text or "Traceback" in text:
                self.original_stderr.write(f'{text}')
            else:
                self.original_stdout.write(f'{text}')

    def flush(self):
        """Flush method for compatibility."""
        self.original_stdout.flush()



    def fileno(self):
        return self.original_stdout.fileno()

    def isatty(self):
        """
        Pretend to be a TTY.
        This is needed for uvicorn to enable colored output.
        """
        return True  # Or False, depending on your needs

    def restore(self):
        """Restore original stdout and stderr."""
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self.running = False


    def read_queue(self):
        """Continuously read from the queue and update the UI log."""
        while self.running:
            try:
                log_message = self.log_queue.get(timeout=0.1)  # Use a timeout
                if self.log_ui is not None:
                    self.log_ui.push(log_message)
            except Empty:
                pass  # Ignore timeout exceptions
            except Exception as e:
                self.original_stderr.write(f"Queue reading error: {e}")
                self.restore()


if __name__ in "__main__":
    # NiceGUI app
    @ui.page('/')
    async def main_page():

        # console false to not generate ui now
        capture = ConsoleCapture(show_console=False)

        with ui.row():
            ui.button('Print Message', on_click=lambda: print('Hello from stdout!'))
            ui.button('Raise Exception', on_click=lambda: 1 / 0)
            ui.button('Send Custom Log', on_click=lambda: capture.log_queue.put("[INFO] Custom log message"))
            ui.button('Restore Console', on_click=capture.restore)

        # generate console ui now
        capture.setup_ui()

    ui.run(reload=False)