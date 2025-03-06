"""
a: zak-45
d: 25/02/2025
v: 1.0.0.0

"""

from multiprocessing.managers import SyncManager
import os
import signal
import psutil
import numpy as np
import time
from src.utl.cv2utils import CV2Utils
from multiprocessing import Queue


import webview
from webview import menu as wm


class WVManager(SyncManager):
    pass

class WebViewManager:
    def __init__(self, sl_ip_address="127.0.0.1", sl_port=60000, authkey=b"wledvideosync"):
        self.address = (sl_ip_address, sl_port)
        self.authkey = authkey
        self.is_running = False
        self.manager = None
        self.pid = None

    def start(self):
        """Starts the WebViewManager.

        Registers the necessary methods with the SyncManager and starts the manager process.
        Prints a confirmation message with the address.
        """

        queue = Queue()

        WVManager.register("create_shared_list", callable=self.create_shared_list)
        WVManager.register("get_shared_lists", callable=self.get_shared_lists)
        WVManager.register("get_shared_lists_info", callable=self.get_shared_lists_info)
        WVManager.register("get_shared_list_info", callable=self.get_shared_list_info)
        WVManager.register("get_server_status", callable=self.get_status)
        WVManager.register("delete_shared_list", callable=self.delete_shared_list)
        WVManager.register("stop_manager", callable=self.stop_manager)
        WVManager.register("start_webview", callable=self.start_webview_process)
        WVManager.register("get_queue", callable=lambda: inputqueue)


        self.manager = WVManager(address=self.address, authkey=self.authkey)
        self.manager.daemon = True
        self.manager.start()

        self.is_running = True
        self.pid = self.manager._process.pid
        print(f"webViewManager started on {self.address} with PID: {self.pid}")


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
            # Check if the manager process exists and is alive
            if self.manager._process and self.manager._process.is_alive():
                os.kill(self.manager._process.pid, signal.SIGTERM)
                print("Manager process has been terminated.")
            else:
                print("Manager process was already stopped or not initialized.")


    def create_shared_list(self, name, width, height, start_time=0):
        pass

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
                print(f"Error deleting shared list '{name}': {e}")
                return False
        else:
            print(f"Shared list '{name}' does not exist.")
            return False


    def clean_shared_list(self, name):
        self.shared_lists[name].shm.close()
        self.shared_lists[name].shm.unlink()
        del self.shared_lists[name]
        del self.shared_lists_info[name]
        print(f"Deleted shared list '{name}'.")
        return True

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

    def start_webview_process(self,window_name='Splash'):
        """
        start a pywebview process and call a window
        :return:
        """
        global webview_process, main_window
        """
        webview_process = Process(target=run_webview, args=(window_name,))
        webview_process.daemon = True
        webview_process.start()
        """

        server_port = 8000
        server_ip = '127.0.0.1'
        keep_running = 'True'
        main_window = None

        # start in blocking mode

        # destroy if exist
        if main_window is not None:
            main_window.destroy()

        # Menu Items definition
        if window_name in ['StopSrv', 'Info', 'BlackOut', 'Details']:
            # minimalist Menu
            menu_items = [
                wm.Menu('Options',
                        [wm.MenuAction('Exit on SysTray', keep_running)]
                        )
            ]
        else:
            # Main menu
            menu_items = [wm.Menu('Main',
                                  [wm.MenuAction('HOME Screen', self.go_to_home)]
                                  ),
                          wm.Menu('Options',
                                  [wm.MenuAction('Keep it running (Put to SysTray)', keep_running)]
                                  )
                          ]

        # Window creation
        if window_name == 'Splash':
            # Main window : splash screen
            main_window = webview.create_window(title=f'WLEDVideoSync {server_port}',
                                                url=f'http://{server_ip}:{server_port}/WLEDVideoSync',
                                                width=1200,
                                                height=720)

        elif window_name == 'Main':
            # Main window : splash screen
            main_window = webview.create_window(title=f'MAIN WLEDVideoSync {server_port}',
                                                url=f'http://{server_ip}:{server_port}',
                                                width=1200,
                                                height=720, text_select=False)

        elif window_name == 'Info':
            # Info window : cast
            main_window = webview.create_window(
                title=f'Cast Info {server_port}',
                url=f"http://{server_ip}:{server_port}/info",
                width=540,
                height=230
            )

        elif window_name == 'BlackOut':
            # Blackout window : show result from api blackout
            if main_window is not None:
                main_window.destroy()
            main_window = webview.create_window(
                title=f'BLACKOUT {server_port}',
                url=f"http://{server_ip}:{server_port}/api/util/blackout",
                width=300,
                height=150
            )

        elif window_name == 'Details':
            # info details and manage window : show result from api CastManage
            if main_window is not None:
                main_window.destroy()
            main_window = webview.create_window(
                title=f'Casts Details {server_port}',
                url=f"http://{server_ip}:{server_port}/DetailsInfo",
                width=640,
                height=480
            )

        elif window_name == 'Player':
            # Run video player
            if main_window is not None:
                main_window.destroy()
            main_window = webview.create_window(
                title=f'Video Player {server_port}',
                url=f"http://{server_ip}:{server_port}/Player",
                width=800,
                height=600
            )

        elif window_name == 'Charts':
            # Page to select charts
            if main_window is not None:
                main_window.destroy()
            main_window = webview.create_window(
                title=f'Run Charts {server_port}',
                url=f"http://{server_ip}:{server_port}/RunCharts",
                width=450,
                height=180
            )

        # start webview
        # To change a default renderer set PYWEBVIEW_GUI environment variable: cef, qt, gtk ...
        webview.start(menu=menu_items, debug=False)

    def keep_running():
        """
        Menu option
        :return:
        """
        global put_on_systray

        put_on_systray = True
        if main_window is not None:
            main_window.destroy()

    def go_to_home(self):
        pass


if __name__ == "__main__":
    ip_address = "127.0.0.1"
    port = 60000
    manager = WebViewManager(ip_address, port)
    manager.start()

    print("Manager started. Waiting for clients...")

    while manager.is_alive():
        time.sleep(2)  # Check every 2 seconds

    print("\nShutting down manager.")
    manager.stop_manager()  # not necessary , but ...
