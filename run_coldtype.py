import multiprocessing
import sys
import io

from coldtype.renderer import Renderer



class RUNColdtype(multiprocessing.Process):
    def __init__(self, log_queue, command_queue):
        super().__init__()
        self.log_queue = log_queue  # Queue for logs
        self.command_queue = command_queue  # Queue for commands
        self._stop = multiprocessing.Event()
        self.stderr_capture = io.StringIO()  # StringIO to capture stderr

    def run(self):
        print("Coldtype process started")

        # Redirect stderr to capture Coldtype's internal stderr output
        original_stderr = sys.stderr
        sys.stderr = self.stderr_capture

        try:
            # Arguments for the Renderer
            args = ["test2.py", "-kl", "fr", "-wcs", "1", "-ec","notepad"]

            # Initialize the Renderer
            _, parser = Renderer.Argparser()
            params = parser.parse_args(args)

            # Use the Renderer class to run Coldtype
            renderer = Renderer(parser=params)

            # Run the Coldtype rendering process
            while not self._stop.is_set():
                renderer.main()  # Keep the rendering loop going

        except Exception as e:
            self.log_queue.put(("stderr", f"Error running Coldtype: {str(e)}"))

        finally:
            # Capture any stderr output from Coldtype after execution
            stderr_output = self.stderr_capture.getvalue()
            if stderr_output:
                self.log_queue.put(("stderr", stderr_output))

            # Restore original stderr
            sys.stderr = original_stderr

    def handle_command(self, command):
        """ Handle commands sent from the main process """
        if command == "exit":
            self._stop.set()  # Stop the Coldtype process gracefully
            self.log_queue.put(("stdout", "Coldtype process exiting..."))

