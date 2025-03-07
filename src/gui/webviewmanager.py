import multiprocessing
import webview


class WebviewManager:
    def __init__(self):
        # List to hold all running webview processes
        self.webview_processes = []

    def open_webview(self, url: str, title: str, width: int, height: int):
        """Open a new webview window."""
        # Create a new process and pass the parameters to it
        process = multiprocessing.Process(target=start_webview, args=(url, title, width, height))
        process.start()
        self.webview_processes.append(process)

    def close_all_webviews(self):
        """Stop all running webview windows."""
        for process in self.webview_processes:
            if process.is_alive():
                process.terminate()
                process.join()
        self.webview_processes.clear()

    def get_running_webviews(self):
        """Get a list of running webview processes."""
        return [process.pid for process in self.webview_processes if process.is_alive()]


def start_webview(url: str, title: str, width: int, height: int):
    """Start a webview window in a separate process."""
    window = webview.create_window(
        title,
        url=url,
        width=width,
        height=height,
        resizable=True
    )
    webview.start()  # Starts the webview window


# Example usage of WebviewManager
if __name__ == '__main__':
    webview_manager = WebviewManager()

    # Open a couple of windows
    webview_manager.open_webview('https://example.com', 'Example Window', 800, 600)
    webview_manager.open_webview('https://another-example.com', 'Another Window', 800, 600)

    print("Running webview windows:", webview_manager.get_running_webviews())

    # Close all windows after some time
    # webview_manager.close_all_webviews()
    # print("Running webview windows after close:", webview_manager.get_running_webviews())
