import contextlib
from nicegui import ui
from src.utl.utils import CASTUtils as Utils
import sys
import threading
from queue import Empty, Full
import time  # Added for sleep
import io  # Import io for type checking

# mp is required
Process, Queue = Utils.mp_setup()


# Helper class to capture a single stream
class StreamCapture:
    """Captures a single stream (stdout/stderr), queues for UI, and passes through."""

    def __init__(self, original_stream: io.TextIOBase, log_queue: Queue, capture_controller: 'ConsoleCapture'):
        """
        Args:
            original_stream: The original sys.stdout or sys.stderr.
            log_queue: The multiprocessing Queue to send captured text to.
            capture_controller: Reference to the main ConsoleCapture instance.
        """
        if not isinstance(original_stream, io.TextIOBase):
            # Fallback if the original stream isn't a standard TextIOBase (e.g., None)
            original_stream = sys.__stderr__  # Default to underlying stderr for safety
        self.original_stream = original_stream
        self.log_queue = log_queue
        self.capture_controller = capture_controller  # To check the 'running' state

    def write(self, text: str):
        """Writes to the original stream and queues the text for the UI log."""
        # --- Queue for UI Log ---
        if self.capture_controller.running and \
                            self.capture_controller._queue_read_thread and \
                            self.capture_controller._queue_read_thread.is_alive():
            try:
                self.log_queue.put(text, block=False)
            except Full:
                # Log internal errors directly to the *original* stream for this capture object
                with contextlib.suppress(Exception):
                    self.original_stream.write("ConsoleCapture queue is full, UI message dropped.\n")
            except Exception as e:
                # Catch potential errors if queue is closed during write attempt
                with contextlib.suppress(Exception):
                    self.original_stream.write(f"ConsoleCapture error writing to UI queue: {e}\n")
        # --- Console Passthrough ---
        # Write to the *original* stream this object is responsible for.
        try:
            self.original_stream.write(text)
        except Exception as e:
            # Fallback write if original stream is broken (rare, but possible during shutdown)
            fallback_stream = sys.__stdout__ if self.original_stream == sys.stdout else sys.__stderr__
            with contextlib.suppress(Exception):
                fallback_stream.write(
                    f"Fallback write error ({'stdout' if fallback_stream == sys.__stdout__ else 'stderr'}): {e}\n{text}")

    def flush(self):
        """Flushes the original stream."""
        with contextlib.suppress(Exception):
            self.original_stream.flush()

    def fileno(self):
        """Returns the fileno of the original stream, or -1 if invalid."""
        try:
            return self.original_stream.fileno()
        except Exception:
            return -1

    def isatty(self):
        """Checks if the original stream is a TTY."""
        try:
            return self.original_stream.isatty()
        except Exception:
            return False


# Main Console Capture class
class ConsoleCapture:
    """Captures and displays console output in a NiceGUI UI using StreamCapture helpers."""

    def __init__(self, show_console=False, text_color='text-white', bg_color='bg-black'):
        """Initialize the ConsoleCapture."""
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.text_color = text_color
        self.bg_color = bg_color
        self.log_ui = None
        self.log_queue = Queue()  # Shared queue for both streams
        self._queue_read_thread = None
        self.running = False
        self.stdout_capture = None  # Placeholder
        self.stderr_capture = None  # Placeholder

        if show_console:
            self.setup_ui()

        self._create_stream_handler()

    def _create_stream_handler(self):
        # Create separate stream handlers AFTER initializing members
        self.stdout_capture = StreamCapture(self.original_stdout, self.log_queue, self)
        self.stderr_capture = StreamCapture(self.original_stderr, self.log_queue, self)

        # Redirect sys streams to our capture objects
        sys.stdout = self.stdout_capture
        sys.stderr = self.stderr_capture

        self._start_read_thread()

    def _start_read_thread(self):
        """Starts the background thread to read from the queue."""
        if not self.running:
            self.running = True
            # Ensure thread is daemon so it doesn't block app exit
            self._queue_read_thread = threading.Thread(target=self.read_queue, daemon=True)
            self._queue_read_thread.start()
            # print('read queue thread started')

    def setup_ui(self):
        """Set up the UI for the console output."""
        # if self.log_ui is None:
        self.log_ui = ui.log(max_lines=100).classes(
                f'console-output w-full h-30 {self.bg_color} {self.text_color}'
            )
        self._start_read_thread()  # Ensure thread is running

        ui.context.client.on_disconnect(self.restore)

    def restore(self):
        """Restore original stdout/stderr and stop the queue reading thread."""
        if not self.running:
            return

        # Restore streams first, checking against the capture objects
        if sys.stdout == self.stdout_capture:
            sys.stdout = self.original_stdout
        if sys.stderr == self.stderr_capture:
            sys.stderr = self.original_stderr

        # Signal the thread to stop
        self.running = False

        # Wait for the thread to finish
        if self._queue_read_thread is not None and self._queue_read_thread.is_alive():
            self._queue_read_thread.join(timeout=2)  # Increased timeout slightly
            if self._queue_read_thread.is_alive():
                # Use original stderr for logging internal issues if possible
                with contextlib.suppress(Exception):
                    self.original_stderr.write("ConsoleCapture: Queue reading thread did not exit gracefully.\n")
        # Clean up the queue
        try:
            while not self.log_queue.empty():
                self.log_queue.get_nowait()
            # Consider close/join_thread if using specific multiprocessing queue types requires it
            # self.log_queue.close()
            # self.log_queue.join_thread()
        except Exception as e:
            with contextlib.suppress(Exception):
                self.original_stderr.write(f"ConsoleCapture: Error cleaning up queue: {e}\n")
        # Use print AFTER restoring stdout
        print("Console streams restored.")

    def read_queue(self):
        """Continuously read from the queue and update the UI log."""
        original_stderr_ref = self.original_stderr  # Local ref in case self.original_stderr changes
        while self.running:
            try:
                log_message = self.log_queue.get(timeout=.1)

                if self.log_ui is not None:
                    try:
                        self.log_ui.push(log_message.strip())
                    except Exception as ui_error:
                        with contextlib.suppress(Exception):
                            original_stderr_ref.write(f"ConsoleCapture: Error updating UI log: {ui_error}\n")
                        self.log_ui = None  # Stop trying to use the potentially broken UI element
            except Empty:
                continue
            except (EOFError, OSError) as e:
                # Errors indicating queue issues, likely during shutdown
                self.log_ui = None  # Stop trying to use the potentially broken UI element
                break  # Exit the loop gracefully
            except Exception as e:
                # Catch other potential errors during get()
                if self.running:  # Avoid logging errors if we are stopping anyway
                    with contextlib.suppress(Exception):
                        original_stderr_ref.write(f"ConsoleCapture: Unexpected queue reading error: {e}\n")
                time.sleep(0.1)  # Avoid busy-waiting on persistent errors

        with contextlib.suppress(Exception):
            # Use original stdout for the final message if possible
            self.original_stdout.write("ConsoleCapture: Queue reading thread finished.\n")


# --- Keep the __main__ block as is ---
if __name__ in "__main__":
    # NiceGUI app
    @ui.page('/')
    async def main_page():
        # console false to not generate ui now
        capture = ConsoleCapture(show_console=False)

        with ui.row():
            ui.button('Print Message', on_click=lambda: print('Hello from stdout!'))
            ui.button('Print Error', on_click=lambda: print('This is an error!', file=sys.stderr))  # Test stderr
            ui.button('Raise Exception', on_click=lambda: 1 / 0)
            ui.button('Send Custom Log', on_click=lambda: capture.log_queue.put("[INFO] Custom log message"))
            ui.button('Shutdown App', on_click=app.shutdown)  # Use NiceGUI shutdown

        # generate console ui now
        capture.setup_ui()

        # Ensure restore is called when the app shuts down
        # app.on_shutdown(capture.restore)


    from nicegui import app  # Ensure app is imported if not already

    ui.run(reload=False)
