"""
a: zak-45
d: 07/03/2025
v: 1.0.0.0

Overview
This Python file provides a WebviewManager class for managing multiple webview windows using the pywebview library.
It allows opening, closing, and tracking the status of multiple webview windows, each running in a separate process.
This is useful for applications that need to display multiple web pages or web-based interfaces concurrently.

Key Components
    WebviewManager Class: This class is the core of the file. It encapsulates the logic for managing webview windows.

open_webview(url, title, width, height):
    Opens a new webview window in a separate process with the specified URL, title, width, and height.
    It uses multiprocessing to avoid blocking the main application thread.

close_all_webviews():
    Closes all running webview windows managed by the instance.
    It iterates through the list of processes and terminates them.

get_running_webviews():
    Returns a list of process IDs for all currently active webview windows.

start_webview(url, title, width, height) Function:
    This helper function is the target for the multiprocessing.
    It creates and starts a single webview window using the provided parameters.
    It's called within a separate process by the open_webview method.

Multiprocessing:
    The code utilizes Python's multiprocessing library to run each webview in its own process.
    This prevents one webview from blocking others and improves the responsiveness of the application.

pywebview Library:
    This file depends on the pywebview library, which is used to create and manage the webview windows.
    It abstracts the underlying webview technologies (like Qt or GTK) and provides a consistent interface.

The example usage at the end of the file demonstrates how to create a WebviewManager instance,
open a couple of webview windows, and retrieve the PIDs of the running windows.
The commented-out code shows how to close all webviews.

"""

import contextlib
from multiprocessing import Pipe
import threading
import webview

from src.utl.utils import CASTUtils as Utils

def start_webview(url: str, title: str, width: int, height: int, conn):
    """
    Starts a new webview window with the specified URL, title, width, and height in a separate process.
    Listens for commands from the parent process to control the window, such as toggling fullscreen or closing the window.

    Args:
        url (str): The URL to load in the webview window.
        title (str): The title of the webview window.
        width (int): The width of the webview window.
        height (int): The height of the webview window.
        conn: The multiprocessing connection object for inter-process communication.
    """
    window = webview.create_window(
        title,
        url=url,
        width=width,
        height=height,
        resizable=True
    )

    # Repeatedly listen for commands in a non-blocking way
    def control_loop(win):
        """
        This loop runs in a separate thread and checks for commands from the parent process.
        It must exit cleanly when the window is destroyed.
        """
        while True:
            try:
                if conn.poll(0.1):  # Use poll with a timeout to avoid busy-waiting
                    cmd = conn.recv()
                    if cmd == "fullscreen":
                        win.toggle_fullscreen()
                    elif cmd.startswith("url="):
                        new_url = cmd[4:]
                        win.load_url(new_url)
                    elif cmd == "exit":
                        break
            except (EOFError, OSError):
                break  # Exit if the parent pipe is closed
        win.destroy()

    # Register loop to run in pywebview main thread, this is blocking
    webview.start(control_loop, window, debug=False)
    # once window closed , close communication
    conn.close()

class WebviewManager:
    """Manages multiple webview windows in separate processes.

    Provides methods for opening, closing, and tracking the status
    of multiple webview windows concurrently.
    """
    # Defer the import of multiprocessing components
    Process = None

    def __init__(self):
        # List to hold all running webview processes
        self.webview_processes = []

        self.webviews = {}  # key: id, value: {"process": ..., "conn": ...}
        self.counter = 0

        # Lazy-load multiprocessing components only when an instance is created
        if WebviewManager.Process is None:
            WebviewManager.Process, _ = Utils.mp_setup()

    def open_webview(self, url: str, title: str, width: int, height: int):
        """Open a new process for a webview window."""

        # inter process communication canal
        parent_conn, child_conn = Pipe()

        # Create a new process and pass the parameters to it, listening canal
        process = self.Process(target=start_webview, args=(url, title, width, height, child_conn,))
        process.daemon = True
        process.start()
        self.webview_processes.append(process)

        wid = self.counter
        self.counter += 1

        # Store process number and communication sending canal
        self.webviews[wid] = {
            "process": process,
            "conn": parent_conn
        }

        # return the wid, so can send command from main thread
        return wid

    def send(self, wid, command: str):
        """Send a command to a running webview process."""
        if wid in self.webviews:
            if conn := self.webviews[wid]["conn"]:
                with contextlib.suppress(BrokenPipeError):
                    conn.send(command)

    # -------------------------------
    #  PUBLIC WINDOW CONTROL METHODS
    # -------------------------------
    def toggle_fullscreen(self, wid):
        """
        Toggles fullscreen mode for the specified webview window.
        Sends a fullscreen command to the webview process to switch its display mode.

        Args:
            wid: The window ID of the webview to toggle fullscreen.
        """
        self.send(wid, "fullscreen")

    def url(self, wid, new_url: str = None):
        """
        Modify the URL on an existing window

        Args:
            wid: The window ID of the webview to change url.
            new_url: The URL to load in the webview window.
        """
        self.send(wid, f"url={new_url}")


    def close(self, wid):
        """
        Closes the specified webview window by sending an exit command to its process.
        Ensures the webview process is instructed to terminate gracefully.

        Args:
            wid: The window ID of the webview to close.
        """
        self.send(wid, "exit")

    def close_all_webviews(self):
        """
        Closes all running webview windows managed by this instance.
        Iterates through all webview processes, sends the exit command, waits for them to close,
        and force-terminates if necessary.
        """
        for wid in list(self.webviews.keys()):
            self.close(wid)
            proc = self.webviews[wid]["process"]
            # Wait for the process to exit gracefully before force-terminating
            proc.join()
            if proc.is_alive():
                # print(f"Webview process {wid} did not close gracefully, terminating.")
                proc.terminate()
            with contextlib.suppress(KeyError):
                del self.webviews[wid]

    def close_all(self):
        """
        Initiates the closure of all running webview windows in a separate thread.
        This allows the main program to continue running while all webview processes are closed in the background.
        """
        thread = threading.Thread(target=self.close_all_webviews)
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()


    def get_running_webviews(self):
        """
        Returns a dictionary of currently active webview windows and their process IDs.
        Only includes webview processes that are still alive.

        Returns:
            dict: A mapping of window IDs to their process IDs for running webview windows.
        """
        return {
            wid: data["process"].pid
            for wid, data in self.webviews.items()
            if data["process"].is_alive()
        }

# Example usage of WebviewManager
if __name__ == '__main__':
    import time

    webview_manager = WebviewManager()

    # Open a couple of windows
    win0 = webview_manager.open_webview('https://example.com', 'Example Window', 600, 400)
    # win1 = webview_manager.open_webview('https://google.com', 'Another Window', 800, 600)

    print("Running webview process windows:", webview_manager.get_running_webviews())

    while True:
        time.sleep(5)
        webview_manager.url(win0)
        time.sleep(2)
        webview_manager.url(win0, 'https://google.com')
        time.sleep(2)
        break

    # Close all windows after some time
    webview_manager.close_all_webviews()
    print("Running webview process windows after close:", webview_manager.get_running_webviews())
