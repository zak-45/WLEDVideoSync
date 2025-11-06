"""
a: zak-45
d: 06/11/2025
v: 1.0.0

Overview:
This file provides a sophisticated console capture utility for NiceGUI applications. It is designed to redirect the
standard output (stdout) and standard error (stderr) streams of a Python application to a `ui.log` element in the
web interface, allowing developers and users to see real-time console output directly in the browser.

This is particularly useful for debugging background processes, threads, or any part of the application that uses
`print()` statements or raises exceptions, without needing to monitor a terminal.

Key Architectural Components:

1.  ConsoleCapture Class:
    -   This is the main public-facing class. It orchestrates the entire capture process.
    -   **Initialization**: When created, it sets up a `multiprocessing.Queue` to act as a thread-safe buffer for log
        messages.
    -   **Stream Redirection**: It replaces `sys.stdout` and `sys.stderr` with instances of the `StreamCapture` helper
        class. This is the core mechanism that intercepts all console output.
    -   **UI Integration**: The `setup_ui()` method creates a `ui.log` element that will display the captured output.
    -   **Background Thread**: It starts a daemon thread (`read_queue`) that continuously reads messages from the queue
        and pushes them to the `ui.log`. This non-blocking design is crucial for keeping the main UI responsive.
    -   **Lifecycle Management**: It includes `restore()` and `recapture()` methods to gracefully stop and restart the
        capturing process, ensuring the original `stdout` and `stderr` are restored correctly.

2.  StreamCapture Class:
    -   This is a helper class that acts as a "file-like object," mimicking the behavior of `sys.stdout`.
    -   **The `write()` Method**: This is the most important part. When any code calls `print()`, this `write()` method
        is invoked. It performs two actions:
        1.  It puts the message into the `log_queue`.
        2.  It passes the message through to the *original* `stdout` or `stderr`, so the output still appears in the
            terminal where the application was launched. This "pass-through" is excellent for debugging.
    -   **Compatibility**: It implements `flush()`, `fileno()`, and `isatty()` to maintain compatibility with libraries
        that expect a standard stream object.
"""
import contextlib
from nicegui import ui
from src.utl.utils import CASTUtils as Utils
import sys
import threading
import time
import io
from queue import Empty, Full

# Helper class to capture a single stream
class StreamCapture:
    """Captures a single stream (stdout/stderr), queues for UI, and passes through."""

    Process, Queue = None, None

    def __init__(self, original_stream: io.TextIOBase, log_queue, capture_controller: 'ConsoleCapture'):
        if not isinstance(original_stream, io.TextIOBase):
            original_stream = sys.__stderr__
        self.original_stream = original_stream
        self.log_queue = log_queue
        self.capture_controller = capture_controller

    def write(self, text: str):
        if self.capture_controller.running and \
                self.capture_controller._queue_read_thread and \
                self.capture_controller._queue_read_thread.is_alive():
            try:
                self.log_queue.put(text, block=False)
            except Full:
                with contextlib.suppress(Exception):
                    self.original_stream.write("ConsoleCapture queue is full, UI message dropped.\n")
            except Exception as e:
                with contextlib.suppress(Exception):
                    self.original_stream.write(f"ConsoleCapture error writing to UI queue: {e}\n")
        try:
            self.original_stream.write(text)
        except Exception as e:
            fallback_stream = sys.__stdout__ if self.original_stream == sys.stdout else sys.__stderr__
            with contextlib.suppress(Exception):
                fallback_stream.write(
                    f"Fallback write error ({'stdout' if fallback_stream == sys.__stdout__ else 'stderr'}): {e}\n{text}")

    def flush(self):
        with contextlib.suppress(Exception):
            self.original_stream.flush()

    def fileno(self):
        try:
            return self.original_stream.fileno()
        except Exception:
            return -1

    def isatty(self):
        try:
            return self.original_stream.isatty()
        except Exception:
            return False

class ConsoleCapture:
    """Captures and displays console output in a NiceGUI UI using StreamCapture helpers."""

    Process, Queue = None, None

    def __init__(self, show_console=False, text_color='text-white', bg_color='bg-black'):
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.text_color = text_color
        self.bg_color = bg_color
        self.log_ui = None
        self._queue_read_thread = None
        self.running = False
        self.stdout_capture = None
        self.stderr_capture = None

        if ConsoleCapture.Queue is None:
            ConsoleCapture.Process, ConsoleCapture.Queue = Utils.mp_setup()

        self.log_queue = self.Queue()

        if show_console:
            self.setup_ui()

        self._create_stream_handler()

    def _create_stream_handler(self):
        self.stdout_capture = StreamCapture(self.original_stdout, self.log_queue, self)
        self.stderr_capture = StreamCapture(self.original_stderr, self.log_queue, self)
        if sys.stdout is not self.stdout_capture:
            sys.stdout = self.stdout_capture
        if sys.stderr is not self.stderr_capture:
            sys.stderr = self.stderr_capture
        self._start_read_thread()

    def _start_read_thread(self):
        if not self.running:
            self.running = True
            self._queue_read_thread = threading.Thread(target=self.read_queue, daemon=True)
            self._queue_read_thread.start()

    def setup_ui(self):
        if self.log_ui is None:
            self.log_ui = ui.log(max_lines=100).classes(
                f'console-output w-full h-30 {self.bg_color} {self.text_color}'
            )
        self._start_read_thread()

    def restore(self):
        """Restore original stdout/stderr and stop the queue reading thread."""
        if not self.running:
            return

        if sys.stdout is self.stdout_capture:
            sys.stdout = self.original_stdout
        if sys.stderr is self.stderr_capture:
            sys.stderr = self.original_stderr

        self.running = False

        if self._queue_read_thread is not None and self._queue_read_thread.is_alive():
            self._queue_read_thread.join(timeout=2)
            if self._queue_read_thread.is_alive():
                with contextlib.suppress(Exception):
                    self.original_stderr.write("ConsoleCapture: Queue reading thread did not exit gracefully.\n")
        try:
            while not self.log_queue.empty():
                self.log_queue.get_nowait()
            self.log_queue.close()
            self.log_queue.join_thread()
        except (OSError, ValueError) as e:
            with contextlib.suppress(Exception):
                self.original_stderr.write(f"ConsoleCapture: Info during queue cleanup (expected on shutdown): {e}\n")
        print("Console streams restored.")

    def recapture(self):
        """Re-enable console UI capture after restore()."""
        if self.running:
            return

        if self.log_queue is None or getattr(self.log_queue, '_closed', False):
            if ConsoleCapture.Queue is None:
                ConsoleCapture.Process, ConsoleCapture.Queue = Utils.mp_setup()
            self.log_queue = self.Queue()

        self.stdout_capture = StreamCapture(self.original_stdout, self.log_queue, self)
        self.stderr_capture = StreamCapture(self.original_stderr, self.log_queue, self)
        sys.stdout = self.stdout_capture
        sys.stderr = self.stderr_capture

        self._start_read_thread()

    def read_queue(self):
        original_stderr_ref = self.original_stderr
        while self.running:
            try:
                log_message = self.log_queue.get(timeout=.1)
                if self.log_ui is not None:
                    try:
                        self.log_ui.push(log_message.strip())
                    except Exception as ui_error:
                        with contextlib.suppress(Exception):
                            original_stderr_ref.write(f"ConsoleCapture: Error updating UI log: {ui_error}\n")
                        self.log_ui = None
            except Empty:
                continue
            except (ValueError, EOFError, OSError):
                self.log_ui = None
                break
            except Exception as e:
                if self.running:
                    with contextlib.suppress(Exception):
                        original_stderr_ref.write(f"ConsoleCapture: Unexpected queue reading error: {e}\n")
                time.sleep(0.1)
        with contextlib.suppress(Exception):
            self.original_stdout.write("ConsoleCapture: Queue reading thread finished.\n")

if __name__ in "__main__":
    from nicegui import app
    @ui.page('/')
    async def main_page():
        capture = ConsoleCapture(show_console=False)

        with ui.row():
            ui.button('Print Message', on_click=lambda: print('Hello from stdout!'))
            ui.button('Print Error', on_click=lambda: print('This is an error!', file=sys.stderr))
            ui.button('Raise Exception', on_click=lambda: 1 / 0)
            ui.button('Send Custom Log', on_click=lambda: capture.log_queue.put("[INFO] Custom log message"))
            ui.button('Shutdown App', on_click=app.shutdown)

        capture.setup_ui()

        # Example: restore and recapture buttons
        with ui.row():
            ui.button('Restore Console', on_click=capture.restore)
            ui.button('Recapture Console', on_click=capture.recapture)

    ui.run(reload=False)
