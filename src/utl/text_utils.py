"""
This utility provides a mixin class for integrating the TextAnimator into different
casting modules (like desktop.py and media.py) without code duplication.

A mixin is a class that provides method implementations for other classes to inherit,
but it is not intended to be instantiated on its own. By having both CASTDesktop and
CASTMedia inherit from TextAnimatorMixin, they both gain the ability to start,
stop, and update text animations using a single, shared set of methods.

Key Components:
- TextAnimatorMixin: A class that contains the core logic for initializing,
  starting, and updating a TextAnimator instance.
"""
from src.txt.textanimator import TextAnimator
from configmanager import LoggerManager

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

    def update_text_animator(self, **kwargs):
        """Updates the parameters of the running TextAnimator instance in real-time."""
        if self.text_animator is not None:
            self.text_animator.update_params(**kwargs)
        else:
            text_utils_logger.warning("TextAnimator is not running, cannot update parameters.")
