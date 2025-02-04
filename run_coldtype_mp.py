import multiprocessing
import sys
import io
import time
import argparse
from coldtype.renderer import Renderer
from multiprocessing.shared_memory import ShareableList


class RUNColdtype(multiprocessing.Process):
    def __init__(self, ilog_queue, shared_list_name):
        super().__init__()
        self.log_queue = ilog_queue  # Queue for logs
        self.shared_list = ShareableList(name=shared_list_name)  # Attach to existing shared list
        self._stop = multiprocessing.Event()
        self.stderr_capture = io.StringIO()  # StringIO to capture stderr

    def run(self):
        print("Coldtype process started")

        original_stderr = sys.stderr
        sys.stderr = self.stderr_capture

        try:
            _, parser = Renderer.Argparser()
            args = ["cold_demo.py", "-kl", "fr", "-wcs", "1", "-ec", "notepad"]
            # params = parser.parse_args(self.shared_list[2:])  # Use shared list for arguments
            params = parser.parse_args(args)
            renderer = Renderer(parser=params)

            while not self._stop.is_set():
                renderer.main()
                self.shared_list[0] = str(int(self.shared_list[0]) + 1)  # Example usage of shared list
                command = self.shared_list[1].strip()
                if command == "exit":
                    self._stop.set()

        except Exception as e:
            self.log_queue.put(("stderr", f"Error running Coldtype: {str(e)}"))

        finally:
            if stderr_output := self.stderr_capture.getvalue():
                self.log_queue.put(("stderr", stderr_output))
            sys.stderr = original_stderr


def log_listener(ilog_queue, i_stop_event, shared_list_name):
    i_shared_list = ShareableList(name=shared_list_name)  # Attach to existing shared list
    while not i_stop_event.is_set():
        if not ilog_queue.empty():
            log_type, message = ilog_queue.get()
            print(f"[{log_type.upper()}] {message}")
            print(f"Shared List Value: {i_shared_list[0]}")  # Example of accessing shared data
        i_command = i_shared_list[1].strip()
        if i_command == "exit":
            stop_event.set()
    i_shared_list.shm.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Run Coldtype with multiprocessing and shared memory.")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments to pass to Coldtype")
    parsed_args = parser.parse_args().args

    log_queue = multiprocessing.Queue()
    shared_list = ShareableList([1, ""] + parsed_args, name="shared_list")  # Store arguments in shared list

    coldtype_process = RUNColdtype(log_queue, "shared_list")
    coldtype_process.start()

    stop_event = multiprocessing.Event()
    listener_process = multiprocessing.Process(target=log_listener, args=(log_queue, stop_event, "shared_list"))
    listener_process.start()

    while coldtype_process.is_alive():
        share_value = str(shared_list[0]).strip()
        print(share_value)
        if share_value == '5':
            print('ok')
            break

    # Set stop flag for both processes
    stop_event.set()
    coldtype_process.join()
    listener_process.join()

    shared_list.shm.close()
    shared_list.shm.unlink()
