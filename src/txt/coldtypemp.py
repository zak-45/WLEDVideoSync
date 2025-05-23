import sys
import os
import time

from datetime import datetime
from coldtype.renderer import Renderer
from multiprocessing.shared_memory import ShareableList
import multiprocessing

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.text')
text_logger = logger_manager.logger


class DualStream:
    def __init__(self, original_stream, queue, stream_name="stdout"):
        """Initialize the DualStream.

        Args:
            original_stream: The original stream (stdout or stderr).
            queue: The queue to write messages to.
            stream_name (str, optional): The name of the stream. Defaults to "stdout".
        """
        self.original_stream = original_stream  # Reference to original stdout/stderr
        self.queue = queue
        self.stream_name = stream_name

    def write(self, message):
        """Write a message to both the original stream and the queue.

        Args:
            message (str): The message to write.
        """
        if message.strip():  # Avoid empty lines
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            formatted_message = f"[{timestamp}] [{self.stream_name}] {message.strip()}"
            self.queue.put(formatted_message)  # Send to log queue
            self.original_stream.write(message+'\n')  # Send to original stdout/stderr

    def flush(self):
        self.original_stream.flush()

class RUNColdtype(multiprocessing.Process):
    """Run the Coldtype renderer in a separate process.

     This method sets up the environment for the Coldtype process,
     redirects stdout and stderr to the log queue if provided,
     and then executes the Coldtype renderer.
     """
    def __init__(self, script_file='', log_queue=None, shared_list_name=None, no_view:bool = False):
        super().__init__()
        self.script_file = script_file
        self.log_queue = log_queue   # Optional log queue for console capture
        self.shared_list = ShareableList(name=shared_list_name) if shared_list_name else None
        self.no_view = no_view


    def run(self):
        """Run the Coldtype renderer in a separate process.

        This method sets up the environment for the Coldtype process,
        redirects stdout and stderr to the log queue if provided,
        and then executes the Coldtype renderer.
        """
        if self.log_queue:
            sys.stdout = DualStream(sys.__stdout__, self.log_queue, stream_name="stdout")
            sys.stderr = DualStream(sys.__stderr__, self.log_queue, stream_name="stderr")

        print("Coldtype process started")

        try:
            # Extract the file name without extension
            script_name = os.path.splitext(os.path.basename(self.script_file))[0]
            # folder to store img
            render_folder = cfg_mgr.app_root_path(f'media/coldtype/{script_name}')
            #
            # call Coldtype with arguments
            if cfg_mgr.app_config is not None:
                keyboard = cfg_mgr.app_config['keyboard']
            else:
                keyboard = 'uk'
            if cfg_mgr.app_config is not None:
                editor = cfg_mgr.app_config['py_editor']
            else:
                editor = 'notepad'
            _, parser = Renderer.Argparser()
            args =[self.script_file,
                   "-kl", keyboard,
                   "-wcs", "1",
                   "-ec", editor,
                   "-of", render_folder,
                   "-nv", str(self.no_view)]
            print(f"Using arguments: {args}")
            params = parser.parse_args(args)
            renderer = Renderer(parser=params)
            print("Running renderer.main()...main Coldtype blocking loop")
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
    cold = RUNColdtype()
    cold.start()

    # Main process loop: Check if Coldtype is still alive
    while cold.is_alive():
        print("Main process can perform tasks here.")
        time.sleep(5)  # Wait 1 second before checking again
        cold.join()


    # Now that Coldtype is finished, we can exit the main process
    print("Coldtype process finished. Main process is now ending.")
    # cold.join()  # Ensure the Coldtype process is properly cleaned up
    print("Main process finished.")
