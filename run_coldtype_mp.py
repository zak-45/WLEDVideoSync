import multiprocessing
import sys
import io
import time

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


def log_listener(log_queue):
    """ Reads logs and prints them in real-time. """
    while True:
        if not log_queue.empty():
            log_type, message = log_queue.get()
            print(f"[{log_type.upper()}] {message}")


def start_terminal_interface(log_queue, command_queue, coldtype_process):
    """ A terminal-based interface to interact with Coldtype. """
    print("Coldtype has started. Enter commands to interact with it or 'exit' to quit.")

    # Start the log listener in a separate process
    listener_process = multiprocessing.Process(target=log_listener, args=(log_queue,))
    listener_process.start()

    # Monitor Coldtype process and wait for it to finish
    while coldtype_process.is_alive():
        # Give some time for the user to enter commands
        command = input("Enter command: ").strip()
        command_queue.put(command)

        if command == "exit":
            listener_process.terminate()  # Stop the listener
            coldtype_process.terminate()  # Stop the Coldtype process
            break

    # Ensure the listener is also terminated when Coldtype exits
    listener_process.terminate()


if __name__ == "__main__":
    multiprocessing.freeze_support()  # Needed for Windows if using multiprocessing

    log_queue = multiprocessing.Queue()
    command_queue = multiprocessing.Queue()

    # Start Coldtype in the background
    coldtype_process = RUNColdtype(log_queue, command_queue)
    coldtype_process.start()

    # Give Coldtype a moment to initialize before starting the terminal interface
    time.sleep(1)

    start_terminal_interface(log_queue, command_queue, coldtype_process)  # Start the terminal interface
