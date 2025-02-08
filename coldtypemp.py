import multiprocessing
import sys
import os
import time

from datetime import datetime
from coldtype.renderer import Renderer
from multiprocessing.shared_memory import ShareableList
from io import StringIO


class StreamToQueue:
    def __init__(self, queue, stream_name="stdout"):
        self.queue = queue
        self.stream_name = stream_name
        self.buffer = StringIO()

    def write(self, message):
        if message.strip():  # Avoid empty lines
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.queue.put(f"[{timestamp}] [{self.stream_name}] {message.strip()}")

    def flush(self):
        pass  # Needed for compatibility with sys.stdout and sys.stderr


class RUNColdtype(multiprocessing.Process):
    def __init__(self, script_file="", log_queue=None, shared_list_name=None):
        super().__init__()
        self.script_file = script_file
        self.log_queue = log_queue   # Optional log queue for console capture
        self.shared_list = ShareableList(name=shared_list_name) if shared_list_name else None

    def run(self):
        if self.log_queue:
            sys.stdout = StreamToQueue(self.log_queue, stream_name="stdout")
            sys.stderr = StreamToQueue(self.log_queue, stream_name="stderr")

        print("Coldtype process started")

        try:
            # Extract the file name without extension
            script_name = os.path.splitext(os.path.basename(self.script_file))[0]
            render_folder = f'media/coldtype/{script_name}'
            _, parser = Renderer.Argparser()

            # Use shared list for arguments if provided, otherwise default args
            args = self.shared_list[2:] if self.shared_list else [
                self.script_file, "-kl", "fr", "-wcs", "1", "-ec", "notepad", "-of", render_folder
            ]
            print(f"Using arguments: {args}")

            params = parser.parse_args(args)
            renderer = Renderer(parser=params)

            print("Running renderer.main()...")
            renderer.main()

        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_msg = f"[{timestamp}] Error running Coldtype:\n{e}"
            print(error_msg)  # This will be captured and sent to the log queue

        finally:
            print("Coldtype process stopped")
            if self.log_queue:
                sys.stdout = sys.__stdout__  # Restore original stdout
                sys.stderr = sys.__stderr__  # Restore original stderr


if __name__ == "__main__":
    process = RUNColdtype()  # No stop_event needed now
    process.daemon = True
    process.start()

    # Main process loop: Check if Coldtype is still alive
    while process.is_alive():
        print("Main process can perform tasks here.")
        time.sleep(5)  # Wait 1 second before checking again
        process.join()


    # Now that Coldtype is finished, we can exit the main process
    print("Coldtype process finished. Main process is now ending.")
    # process.join()  # Ensure the Coldtype process is properly cleaned up
    print("Main process finished.")
