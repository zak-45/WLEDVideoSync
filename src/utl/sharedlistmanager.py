"""
a: zak-45
d: 25/02/2025
v: 1.0.0.0

Overview
This Python code implements a SharedListManager class that facilitates the creation, access,
and management of shared memory lists in a multiprocessing environment.
It leverages the multiprocessing.shared_memory and multiprocessing.managers modules to allow multiple processes
to concurrently access and modify the same data. This is particularly useful for sharing large data structures,
such as images or video frames, between processes without the overhead of copying data.
The manager runs as a separate process, providing a centralized service for managing these shared lists.

Key Components
SharedListManager Class: This class is the core of the code, providing methods for:

start(): Starts the manager server, making it available for client connections.
create_shared_list(): Creates a new shared list with a specified name, width, and height.
    It initializes the shared memory with a numpy array filled with 255 values (white image).
get_shared_lists(): Returns a list of names of the currently managed shared lists.
get_shared_lists_info(): Returns a dictionary containing information (width and height) about each shared list.
get_shared_list_info(): Returns the width and height of a specific shared list.
delete_shared_list(): Deletes a shared list, freeing the associated shared memory.
stop_manager(): Stops the manager server and cleans up resources.
is_alive(): Checks if the manager process is still running.
SLManager Class: A custom SyncManager that registers the SharedListManager's methods,
                enabling remote access from other processes.

Use of ShareableList:
The code utilizes multiprocessing.shared_memory.ShareableList to create and manage the shared lists.
This ensures that the underlying memory is properly shared and synchronized between processes.

Error Handling and Resource Management:
The code includes error handling to gracefully manage situations like attempting to create a list with a name
that already exists or deleting a non-existent list.
It also ensures proper cleanup of shared memory when the manager is stopped or a list is deleted.

Main Execution Block (if __name__ == "__main__":):
This block demonstrates how to instantiate and use the SharedListManager.
It starts the manager, waits for clients to connect, and then shuts down the manager gracefully.
"""

from multiprocessing.managers import SyncManager
from multiprocessing.shared_memory import ShareableList
import os
import signal
import psutil
import numpy as np
import time
from src.utl.cv2utils import CV2Utils

from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.slmanager')
slmanager_logger = logger_manager.logger


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
        slmanager_logger.info(f"SharedListManager started on {self.address} with PID: {self.pid}")


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

        slmanager_logger.info("Shutting down the SharedListManager...")

        if self.manager:
            # Cleanup shared lists before shutdown
            for name in list(self.shared_lists.keys()):
                self.delete_shared_list(name)

            slmanager_logger.info("Cleaning up shared lists...")

            # Check if the manager process exists and is alive
            if self.manager._process and self.manager._process.is_alive():
                os.kill(self.manager._process.pid, signal.SIGTERM)
                slmanager_logger.info("Manager process has been terminated.")
            else:
                slmanager_logger.warning("Manager process was already stopped or not initialized.")


    def create_shared_list(self, name, width, height, start_time=0):
        """Creates a new shared list.

        Creates a shared list with the given name, size, and default value, using
        multiprocessing.shared_memory.ShareableList.  Handles existing lists and potential errors.
        """

        if name in self.shared_lists:
            slmanager_logger.info(f"Shared list '{name}' already exists, nothing to do.")
            return None  # Return None if exist

        # ShareAbleList need a fixed amount of memory, size need to be calculated for max
        # Create a (x, y, 3) array with all values set to 111 to reserve memory
        full_array = np.full((width,height,3), 111, dtype=np.uint8)
        size = full_array.nbytes
        # to bypass ShareAbleList bug
        full_array = CV2Utils.frame_add_one(full_array)

        try:
            self.shared_lists[name] = ShareableList([full_array, start_time], name=name)
            self.shared_lists_info[name] = {"w":width, "h":height}
            slmanager_logger.info(f"Created shared list '{name}'  for : {width} - {height} of size {size}.")
            return True

        except Exception as e:
            slmanager_logger.error(f"Error creating shared list '{name}': {e}")
            return False  # Return False on failure

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
        """Deletes a ShareableList and free shared memory."""

        if name in self.shared_lists:
            try:
                return self.clean_shared_list(name)
            except Exception as e:
                slmanager_logger.error(f"Error deleting shared list '{name}': {e}")
                return False
        else:
            slmanager_logger.warning(f"Shared list '{name}' does not exist.")
            return False


    def clean_shared_list(self, name):
        self.shared_lists[name].shm.close()
        self.shared_lists[name].shm.unlink()
        del self.shared_lists[name]
        del self.shared_lists_info[name]
        slmanager_logger.info(f"Deleted shared list '{name}'.")
        return True

    def is_alive(self):
        """Checks if the manager process is alive."""
        try:
            return psutil.pid_exists(self.pid) and psutil.Process(self.pid).is_running()
        except psutil.NoSuchProcess:
            slmanager_logger.info(f"process: {self.pid} do not exist")
            return False
        except psutil.AccessDenied:
            slmanager_logger.error("Access denied")
            return False
        except Exception as e:
            slmanager_logger.error(f"Error checking process: {e}")
            return False


if __name__ == "__main__":
    ip_address = "127.0.0.1"
    port = 50000
    manager = SharedListManager(ip_address, port)
    manager.start()

    slmanager_logger.info("Manager started. Waiting for clients...")

    while manager.is_alive():
        time.sleep(2)  # Check every 2 seconds

    slmanager_logger.info("\nShutting down manager.")
    manager.stop_manager()  # not necessary , but ...
