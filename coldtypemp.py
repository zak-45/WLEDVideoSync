import multiprocessing
import sys
import os
import io
import time
from datetime import datetime
from coldtype.renderer import Renderer
from multiprocessing.shared_memory import ShareableList


class DualStream(io.StringIO):
    """Custom stream that writes to both stdout and stderr."""

    def __init__(self, original_stream, capture_stream):
        super().__init__()
        self.original_stream = original_stream
        self.capture_stream = capture_stream

    def write(self, message):
        # Write to the original stream (console)
        self.original_stream.write(message)
        self.original_stream.flush()

        # Write to the capture stream (for logging)
        self.capture_stream.write(message)
        self.capture_stream.flush()

    def flush(self):
        self.original_stream.flush()
        self.capture_stream.flush()


class RUNColdtype(multiprocessing.Process):
    def __init__(self, script_file="", log_queue=None, shared_list_name=None):
        super().__init__()
        self.script_file = script_file
        self.log_queue = log_queue  # Optional queue for logs
        self.shared_list = ShareableList(name=shared_list_name) if shared_list_name else None
        self._stop = multiprocessing.Event()  # Event to signal when to stop
        self.stderr_capture = io.StringIO()
        self.stdout_capture = io.StringIO()

    def run(self):
        print("Coldtype process started")

        original_stderr = sys.stderr
        original_stdout = sys.stdout

        # Create DualStream that writes to both the console and our capture buffers
        sys.stderr = DualStream(original_stderr, self.stderr_capture)
        sys.stdout = DualStream(original_stdout, self.stdout_capture)

        try:

            # Extract the file name without extension
            script_name =  os.path.splitext(os.path.basename(self.script_file))[0]
            render_folder = f'media/coldtype/{script_name}'
            _, parser = Renderer.Argparser()
            # Use shared list for arguments if provided, otherwise default args
            args = self.shared_list[2:] if self.shared_list else [self.script_file, "-kl", "fr", "-wcs", "1", "-ec",
                                                                  "notepad", "-of", render_folder]
            print(f"Using arguments: {args}")  # Debugging line
            params = parser.parse_args(args)
            renderer = Renderer(parser=params)

            while not self._stop.is_set():
                print("Running renderer.main()...")  # Debugging line
                renderer.main()

                # Flush captured stdout and stderr to the real console
                self._flush_stdout()
                self._flush_stderr()

                # Check shared list for 'exit' command
                if self.shared_list and self.shared_list[1].strip() == "exit":
                    print("Exit command received.")  # Debugging line
                    # renderer.signal_shutdown(signal.SIGINT)
                    self._stop.set()

                time.sleep(0.1)

            print("Coldtype process finished normally.")  # Debugging line

        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_msg = f"[{timestamp}] Error running Coldtype: {str(e)}"
            print(error_msg)  # Print error message to the console
            if self.log_queue:
                self.log_queue.put(("stderr", error_msg))

        finally:
            sys.stderr = original_stderr
            sys.stdout = original_stdout
            print("Coldtype process stopped")

    def _flush_stdout(self):
        """Flush captured stdout to the real console."""
        if stdout_output := self._get_stdout_output():
            print(stdout_output)  # Directly print captured stdout to console
            if self.log_queue:
                self.log_queue.put(("stdout", stdout_output))

    def _flush_stderr(self):
        """Flush captured stderr to the real console."""
        if stderr_output := self._get_stderr_output():
            print(stderr_output, file=sys.stderr)  # Directly print captured stderr to console
            if self.log_queue:
                self.log_queue.put(("stderr", stderr_output))

    def _get_stdout_output(self):
        """Retrieve and clear stdout buffer."""
        self.stdout_capture.seek(0)
        output = self.stdout_capture.read()
        self.stdout_capture.truncate(0)
        self.stdout_capture.seek(0)
        return output.strip() if output else None

    def _get_stderr_output(self):
        """Retrieve and clear stderr buffer."""
        self.stderr_capture.seek(0)
        output = self.stderr_capture.read()
        self.stderr_capture.truncate(0)
        self.stderr_capture.seek(0)
        return output.strip() if output else None


if __name__ == "__main__":
    process = RUNColdtype()  # No stop_event needed now
    process.daemon = True
    process.start()

    # Main process loop: Check if Coldtype is still alive
    while process.is_alive():
        print("Main process can perform tasks here.")
        time.sleep(5)  # Wait 1 second before checking again
        process.terminate()

    # Now that Coldtype is finished, we can exit the main process
    print("Coldtype process finished. Main process is now ending.")
    process.join()  # Ensure the Coldtype process is properly cleaned up
    print("Main process finished.")
