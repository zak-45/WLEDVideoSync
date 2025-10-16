"""
This utility provides a mixin class for integrating the TextAnimator into different
casting modules (like desktop.py and media.py) without code duplication.
It also includes a NiceGUI page (`text_page`) that serves as a dynamic control
panel for editing the `TextAnimator`'s parameters in real-time.

A mixin is a class that provides method implementations for other classes to inherit,
but it is not intended to be instantiated on its own. By having both CASTDesktop and
CASTMedia inherit from TextAnimatorMixin, they both gain the ability to start,
stop, and update text animations using a single, shared set of methods.

Key Components:
- TextAnimatorMixin: A class that contains the core logic for initializing,
  starting, and updating a TextAnimator instance.
- text_page: A NiceGUI page that allows users to graphically edit all parameters
  of a running TextAnimator instance and apply them.
"""
import shelve
import ast
from nicegui import ui, app
from src.txt.textanimator import TextAnimator
from configmanager import LoggerManager, WLED_PID_TMP_FILE

logger_manager = LoggerManager(logger_name='WLEDLogger.text_utils')
text_utils_logger = logger_manager.logger

class TextAnimatorMixin:
    """A mixin class to provide TextAnimator functionality to casting classes."""

    def init_text_animator(self):
        """Initializes the TextAnimator instance."""
        self.text_animator = None
        if self.overlay_text:
            text_to_display = self.anim_text or "WLEDVideoSync"
            try:
                self.text_animator = TextAnimator(
                    text=text_to_display,
                    width=self.scale_width,
                    height=self.scale_height,
                    speed=50,
                    direction="left",
                    font_path=self.font_path,
                    font_size=self.font_size,
                    color=(255, 255, 255),  # BGR White
                    fps=self.rate,
                    effect="rainbow_cycle"
                )
                text_utils_logger.info("TextAnimator initialized.")
            except Exception as e:
                text_utils_logger.error(f"Failed to initialize TextAnimator: {e}")
                self.text_animator = None

    def start_text_animator(self):
        """Starts the TextAnimator instance."""
        if not self.overlay_text:
            text_utils_logger.warning("TextAnimator is not allowed to run.")
        else:
            if self.text_animator is not None:
                text_utils_logger.warning("TextAnimator is already running, cannot start again.")
            else:
                self.init_text_animator()

    def stop_text_animator(self):
        """Stop the TextAnimator instance."""
        self.text_animator = None
        text_utils_logger.info("TextAnimator stopped.")

    def update_text_animator(self, **kwargs):
        """Updates the parameters of the running TextAnimator instance in real-time."""
        if self.text_animator is not None:
            self.text_animator.update_params(**kwargs)
        else:
            text_utils_logger.warning("TextAnimator is not running, cannot update parameters.")
