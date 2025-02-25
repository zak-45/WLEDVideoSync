from multiprocessing.managers import SyncManager
from multiprocessing.shared_memory import ShareableList
import os
import signal
import psutil
import numpy as np
import time
from src.utl.cv2utils import CV2Utils

class SLManager(SyncManager):
    """Custom SyncManager for SharedListManager.

    Provides a base for registering and managing shared lists.
    """
    pass

class SharedListManager:
    """Manages shared lists in a multiprocessing environment.

    Provides methods for creating, accessing, updating, and deleting shared lists using
    multiprocessing.shared_memory.ShareableList.  Handles manager startup and shutdown.
    """

    def __init__(self, sl_ip_address="127.0.0.1", sl_port=50000, authkey=b"wledvideosync"):
        """Initializes SharedListManager with address and authentication key.

        Sets up the manager's address, authentication key, and initializes an empty dictionary to store shared lists.
        """
        self.address = (sl_ip_address, sl_port)
        self.authkey = authkey
        self.shared_lists = {}
        self.shared_lists_info = {}
        self.is_running = False
        self.manager = None
        self.pid = None

    def start(self):
        """Starts the SharedListManager.

        Registers the necessary methods with the SyncManager and starts the manager process.
        Prints a confirmation message with the address.
        """
        SLManager.register("create_shared_list", callable=self.create_shared_list)
        SLManager.register("get_shared_lists", callable=self.get_shared_lists)
        SLManager.register("get_shared_lists_info", callable=self.get_shared_lists_info)
        SLManager.register("get_shared_list_info", callable=self.get_shared_list_info)
        SLManager.register("get_server_status", callable=self.get_status)
        SLManager.register("delete_shared_list", callable=self.delete_shared_list)
        SLManager.register("stop_manager", callable=self.stop_manager)

        self.manager = SLManager(address=self.address, authkey=self.authkey)
        self.manager.start()
        self.is_running = True
        self.pid = self.manager._process.pid
        print(f"SharedListManager started on {self.address} with PID: {self.pid}")


    def get_pid(self):
        """Returns the process ID (PID) of the manager process.

        Retrieves and returns the PID of the manager process.
        """
        return self.manager._process.pid

    def get_status(self):
        return self.is_running

    def stop_manager(self):
        """Stops the SharedListManager.

        Cleans up shared lists, terminates the manager process, and prints status messages.
        """

        print("Shutting down the SharedListManager...")

        if self.manager:
            # Cleanup shared lists before shutdown
            for name in list(self.shared_lists.keys()):
                self.delete_shared_list(name)

            print("Cleaning up shared lists...")

            # Check if the manager process exists and is alive
            if self.manager._process and self.manager._process.is_alive():
                os.kill(self.manager._process.pid, signal.SIGTERM)
                print("Manager process has been terminated.")
            else:
                print("Manager process was already stopped or not initialized.")


    def create_shared_list(self, name, width, height, start=0):
        """Creates a new shared list.

        Creates a shared list with the given name, size, and default value, using
        multiprocessing.shared_memory.ShareableList.  Handles existing lists and potential errors.
        """

        if name in self.shared_lists:
            print(f"Shared list '{name}' already exists.")
            return False

        # Create a (x, y, 3) array with all values set to 255 to reserve memory
        full_array = np.full((width,height,3), 255, dtype=np.uint8)
        full_array_bytes = CV2Utils.frame_add_one(full_array)

        try:
            self.shared_lists[name] = ShareableList([full_array_bytes, start], name=name)
            self.shared_lists_info[name] = {"w":width, "h":height}
            print(f"Created shared list '{name}'  for : {width} - {height} of size {full_array.nbytes}.")
            return True

        except Exception as e:
            print(f"Error creating shared list '{name}': {e}")
            return None  # Return None on failure

    def get_shared_lists(self):
        """Return the list of shared list names."""
        return list(self.shared_lists.keys())

    def get_shared_lists_info(self):
        """Return the list of shared list names with w & h."""
        return self.shared_lists_info

    def get_shared_list_info(self, name):
        """Return  w & h for a shared list name."""
        return self.shared_lists_info[name]

    def delete_shared_list(self, name):
        """Deletes a ShareableList and frees shared memory."""

        if name in self.shared_lists:
            try:
                self.shared_lists[name].shm.close()
                self.shared_lists[name].shm.unlink()
                del self.shared_lists[name]
                del self.shared_lists_info[name]
                print(f"Deleted shared list '{name}'.")
            except Exception as e:
                print(f"Error deleting shared list '{name}': {e}")
        else:
            print(f"Shared list '{name}' does not exist.")


    def is_alive(self):
        """Checks if the manager process is alive."""
        try:
            return psutil.pid_exists(self.pid) and psutil.Process(self.pid).is_running()
        except psutil.NoSuchProcess:
            print(f"process: {self.pid} do not exist")
            return False
        except psutil.AccessDenied:
            print("Access denied")
            return False
        except Exception as e:
            print(f"Error checking process: {e}")
            return False


if __name__ == "__main__":
    ip_address = "127.0.0.1"
    port = 50000
    manager = SharedListManager(ip_address, port)
    manager.start()

    print("Manager started. Waiting for clients...")

    while manager.is_alive():
        time.sleep(2)  # Check every 2 seconds

    print("\nShutting down manager.")
    manager.stop_manager()  # not necessary , but ...
