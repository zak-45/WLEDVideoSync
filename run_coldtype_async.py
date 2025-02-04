import asyncio
import signal
import logging
import sys
import threading
from io import StringIO
from coldtype.renderer import Renderer

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("coldtype_runner.log"),
        logging.StreamHandler()
    ]
)


class RUNColdtype:
    def __init__(self):
        self.rate: int = 25
        self.renderer = None  # Store Renderer instance
        self.stdout_backup = sys.stdout
        self.stderr_backup = sys.stderr
        self.stdout_capture = StringIO()
        self.stderr_capture = StringIO()
        self.running = False  # Flag to track execution
        self.loop = None  # Store event loop reference
        self.thread = None  # Store event loop thread
        logging.info("RUNColdtype initialized")

    def renderer_thread(self):
        """Runs Renderer.main() inside a thread while capturing stdout and stderr in real time."""
        logging.info("Starting Coldtype Renderer thread...")

        try:
            _, parser = Renderer.Argparser()
            params = parser.parse_args(["cold_demo.py", "-wcs", "1", "-ec", "notepad"])
            self.renderer = Renderer(parser=params)

            # Redirect stdout and stderr
            sys.stdout = self.stdout_capture
            sys.stderr = self.stderr_capture
            self.running = True

            self.renderer.main()  # Blocking call

        except Exception as e:
            logging.error(f"Error in Renderer thread: {e}")
        finally:
            self.running = False

    async def capture_output(self):
        """Continuously reads stdout and stderr in real time."""
        logging.info("Capturing Renderer output in real time...")

        while self.running:
            await asyncio.sleep(0.1)  # Adjust the interval for better performance

            stdout_content = self.stdout_capture.getvalue()
            stderr_content = self.stderr_capture.getvalue()

            if stdout_content:
                logging.info(f"[Coldtype stdout]: {stdout_content.strip()}")
                self.stdout_capture.truncate(0)
                self.stdout_capture.seek(0)

            if stderr_content:
                logging.error(f"[Coldtype stderr]: {stderr_content.strip()}")
                self.stderr_capture.truncate(0)
                self.stderr_capture.seek(0)

    async def stop_coldtype(self):
        """Stops the Renderer gracefully."""
        if self.renderer:
            logging.info("Stopping Coldtype Renderer...")
            try:
                self.renderer.should_exit = True  # Signal the renderer to exit
                await asyncio.sleep(1)  # Allow time for shutdown
                logging.info("Coldtype Renderer stopped.")
            except Exception as e:
                logging.error(f"Error stopping Coldtype Renderer: {e}")

            # Restore stdout and stderr
            sys.stdout = self.stdout_backup
            sys.stderr = self.stderr_backup

        # Stop event loop
        if self.loop and self.loop.is_running():
            self.loop.stop()
            logging.info("Async event loop stopped.")

    def start_async(self):
        """Starts the asyncio event loop in a background thread (non-blocking)."""

        def run_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.capture_output())

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()

    def start(self):
        """Starts the Coldtype Renderer in a separate thread without blocking the main script."""
        renderer_thread = threading.Thread(target=self.renderer_thread, daemon=True)
        renderer_thread.start()

        self.start_async()  # Start the event loop in a background thread

        logging.info("Coldtype Renderer started (non-blocking).")

    def stop(self):
        """Stops Coldtype manually from the main script."""
        if self.running:
            logging.info("Manual stop requested...")
            asyncio.run(self.stop_coldtype())  # Stop async tasks
            if self.thread and self.thread.is_alive():
                self.thread.join()  # Ensure background thread stops
            logging.info("Coldtype has been stopped.")


# Run Coldtype
if __name__ == "__main__":
    cold_runner = RUNColdtype()
    cold_runner.start()

    # Main script continues
    print("Main script is running. Press ENTER to stop Coldtype.")
    input()  # Wait for user input

    cold_runner.stop()  # Stop Coldtype manually
    print("Coldtype stopped. Main script exiting.")
