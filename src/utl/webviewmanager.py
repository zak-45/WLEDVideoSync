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

import webview

from src.utl.utils import CASTUtils as Utils

def start_webview(url: str, title: str, width: int, height: int):
    """Start a webview window in a separate process."""
    webview.create_window(
        title,
        url=url,
        width=width,
        height=height,
        resizable=True
    )
    webview.start()  # Starts the webview window

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

        # Lazy-load multiprocessing components only when an instance is created
        if WebviewManager.Process is None:
            WebviewManager.Process, _ = Utils.mp_setup()

    def open_webview(self, url: str, title: str, width: int, height: int):
        """Open a new process for a webview window."""
        # Create a new process and pass the parameters to it
        process = self.Process(target=start_webview, args=(url, title, width, height))
        process.daemon = True
        process.start()
        self.webview_processes.append(process)

    def close_all_webviews(self):
        """Stop all running processes with webview windows."""
        for process in self.webview_processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        self.webview_processes.clear()
        print('Stop all running webview processes')

    def get_running_webviews(self):
        """Get a list of running webview processes."""
        return [process.pid for process in self.webview_processes if process.is_alive()]


# Example usage of WebviewManager
if __name__ == '__main__':
    import time

    webview_manager = WebviewManager()

    # Open a couple of windows
    webview_manager.open_webview('https://example.com', 'Example Window', 800, 600)
    webview_manager.open_webview('https://google.com', 'Another Window', 800, 600)

    print("Running webview process windows:", webview_manager.get_running_webviews())

    while True:
        time.sleep(10)
        break

    # Close all windows after some time
    webview_manager.close_all_webviews()
    print("Running webview process windows after close:", webview_manager.get_running_webviews())
