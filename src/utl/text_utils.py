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


async def text_page(class_obj=None):
    """
    A NiceGUI page to dynamically edit the parameters of a TextAnimator instance.
    """

    def bgr_to_hex(bgr_tuple):
        """Converts a (B, G, R) tuple to a hex color string."""
        if not bgr_tuple:
            return '#000000'
        b, g, r = bgr_tuple
        return f'#{r:02x}{g:02x}{b:02x}'

    def hex_to_bgr(hex_str):
        """Converts a hex color string to a (B, G, R) tuple."""
        hex_str = hex_str.lstrip('#')
        r, g, b = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        return b, g, r

    """
    A NiceGUI page to dynamically edit the parameters of a TextAnimator instance.
    """
    ui.label('Text Animator Control Panel').classes('text-2xl self-center')

    # Retrieve the target object (Desktop or Media) from the shelve file
    class_obj = class_obj
    if class_obj is None or class_obj.text_animator is None:
        ui.label("No active TextAnimator to configure. Start a cast with text overlay first.").classes('text-lg self-center text-warning')
        return

    animator = class_obj.text_animator
    params = {}

    def gather_params():
        """Collects all values from UI controls into a dictionary."""
        params['text'] = text_input.value
        params['speed'] = speed_input.value
        params['direction'] = direction_select.value
        params['color'] = hex_to_bgr(color_input.value)
        params['font_size'] = font_size_input.value
        params['bg_color'] = hex_to_bgr(bg_color_input.value) if (bg_color_input.value and bg_toggle.value) else None
        params['opacity'] = opacity_slider.value
        params['effect'] = effect_select.value if effect_select.value != 'none' else None
        params['align'] = align_select.value
        params['vertical_align'] = vertical_align_select.value
        params['y_offset'] = y_offset_input.value
        params['shadow'] = shadow_toggle.value
        params['shadow_color'] = hex_to_bgr(shadow_color_input.value)
        params['shadow_offset'] = (shadow_offset_x.value, shadow_offset_y.value)
        params['explode_speed'] = explode_speed_input.value
        params['blink_interval'] = blink_interval_input.value
        params['color_change_interval'] = color_change_interval_input.value
        params['explode_pre_delay'] = explode_pre_delay_input.value

    def apply_changes():
        """Applies the collected parameters to the TextAnimator."""
        gather_params()
        class_obj.update_text_animator(**params)
        ui.notify('TextAnimator parameters updated!', type='positive')

    with ui.card().classes('w-full'):
        with ui.grid(columns=3).classes('gap-4'):
            # --- Core Parameters ---
            text_input = ui.textarea('Text', value=animator.text).props('autogrow')
            speed_input = ui.number('Speed (px/s)', value=animator.speed, min=0, step=10)
            direction_select = ui.select(['left', 'right', 'up', 'down', 'none'], label='Direction', value=animator.direction)
            font_size_input = ui.number('Font Size', value=animator.font_size, min=1, step=1)
            
            # Create the slider and bind its value to the animator's opacity
            opacity_slider = ui.slider(min=0.0, max=1.0, step=0.05, value=animator.opacity).props('label-always')
            # Bind the label's text to the slider's value, formatting it on the fly
            ui.label().bind_text_from(opacity_slider, 'value', lambda v: f'Opacity: {v:.2f}')

            # --- Color Parameters ---
            color_input = ui.color_input('Text Color', value=bgr_to_hex(animator.color))
            bg_color_input = ui.color_input('Background Color', value=bgr_to_hex(animator.bg_color))
            bg_toggle = ui.switch('Background', value=False)

            # --- Alignment ---
            align_select = ui.select(['left', 'center', 'right'], label='Horizontal Align', value=animator.align)
            vertical_align_select = ui.select(['top', 'center', 'bottom'], label='Vertical Align', value=animator.vertical_align)
            y_offset_input = ui.number('Vertical Offset', value=animator.y_offset, step=1)

            # --- Shadow ---
            with ui.column():
                shadow_toggle = ui.switch('Shadow', value=animator.shadow)
                shadow_color_input = ui.color_input('Shadow Color', value=bgr_to_hex(animator.shadow_color))
                with ui.row():
                    shadow_offset_x = ui.number('Shadow X', value=animator.shadow_offset[0])
                    shadow_offset_y = ui.number('Shadow Y', value=animator.shadow_offset[1])

            # --- Effects ---
            effect_select = ui.select(
                ['none', 'blink', 'color_cycle', 'rainbow_cycle', 'explode', 'wave', 'shake', 'scale', 'particle'],
                label='Effect', value=animator.effect or 'none'
            )

            # --- Effect-Specific Parameters ---
            with ui.card().bind_visibility_from(effect_select, 'value', value='blink'):
                blink_interval_input = ui.number('Blink Interval (s)', value=animator.blink_interval, min=0.1, step=0.1)

            with ui.card().bind_visibility_from(effect_select, 'value', value='color_cycle'):
                color_change_interval_input = ui.number('Color Change Interval (s)', value=animator.color_change_interval, min=0.1, step=0.1)

            with ui.card().bind_visibility_from(effect_select, 'value', value='explode'):
                explode_speed_input = ui.number('Explode Speed', value=animator.explode_speed, min=1, step=1)
                explode_pre_delay_input = ui.number('Explode Pre-Delay (s)', value=animator.explode_pre_delay, min=0.0, step=0.1)

    ui.button('Apply Changes', on_click=apply_changes).classes('mt-4 self-center')
