from nicegui import ui
import sys
import multiprocessing
import threading
import time

class ConsoleCapture:
    def __init__(self):
        self.original_stdout = sys.stdout
        self.log_ui = None
        self.log_queue = multiprocessing.Queue()

        sys.stdout = self

        # Start a background thread to read from the queue
        self.running = True
        threading.Thread(target=self.read_queue, daemon=True).start()

    def write(self, text):
        if text.strip():
            self.log_queue.put(text.strip())  # Send to the queue
            self.original_stdout.write(text)

    def flush(self):
        """Flush method for compatibility."""
        pass

    def setup_ui(self):
        self.log_ui = ui.log()
        self.log_ui.classes('w-full h-30')

    def read_queue(self):
        """Continuously read from the queue and update the UI log."""
        while self.running:
            try:
                while not self.log_queue.empty():
                    log_message = self.log_queue.get()
                    if self.log_ui is not None:
                        self.log_ui.push(log_message)
            except Exception as e:
                print(f"Queue reading error: {e}\n")
            time.sleep(0.1)  # Prevent busy waiting


if __name__ in {"__main__", "__mp_main__"}:
    # NiceGUI app
    @ui.page('/')
    async def main_page():

        capture = ConsoleCapture()

        with ui.column():
            ui.button('Print Message', on_click=lambda: print('Hello from stdout!'))
            ui.button('Send Custom Log', on_click=lambda: capture.log_queue.put("[INFO] Custom log message"))

        capture.setup_ui()

    ui.run(reload=False)

