import time
from typing import Optional, Tuple
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.text')
text_logger = logger_manager.logger

class BackgroundOverlay:
    """
    The BackgroundOverlay class manages a background image and provides methods to create a tiled version of it
    and overlay other images on top. It handles RGBA images correctly, respecting the alpha channel for transparency.
    If the overlaid image doesn't have an alpha channel, it's treated as a regular BGR image.
    """
    def __init__(self, background_path):
        # Load and prepare the tiled background
        self.background_image = Image.open(background_path).convert("RGBA")
        self.bg_np = np.array(self.background_image)
        bgr = self.bg_np[..., :3]
        alpha = self.bg_np[..., 3]
        bg_alpha_scaled = alpha[:, :, np.newaxis] / 255.0
        self.background = (bgr * bg_alpha_scaled + 255 * (1 - bg_alpha_scaled)).astype(np.uint8)

    def get_tiled_background(self, window_width, window_height):
        """Creates a tiled background image.

        Tiles the loaded background image to fit the specified dimensions.
        """
        # Create the tiled background to fill the window
        tiled_background = np.zeros((window_height, window_width, 3), dtype=np.uint8)
        tile_height, tile_width = self.background.shape[:2]

        for y in range(0, window_height, tile_height):
            for x in range(0, window_width, tile_width):
                tiled_background[y:y + tile_height, x:x + tile_width] = self.background[
                                                                        :min(tile_height, window_height - y),
                                                                        :min(tile_width, window_width - x)]

        return tiled_background

    def apply_background(self, i_frame):
        """Overlays the input frame onto the tiled background.

        Combines the tiled background with the given frame, respecting the frame's alpha channel if present.
        """
        # Get the window size and tile the background
        window_height, window_width = i_frame.shape[:2]
        tiled_background = self.get_tiled_background(window_width, window_height)

        # Combine the background with the frame (overlay frame on top)
        combined_frame = np.copy(tiled_background)

        # Assume the frame has an alpha channel (RGBA), otherwise convert to RGB
        if i_frame.shape[2] == 4:
            alpha = i_frame[..., 3] / 255.0  # Get the alpha channel of the frame
            for y in range(window_height):
                for x in range(window_width):
                    if alpha[y, x] > 0:  # Only overwrite where the frame is non-transparent
                        combined_frame[y, x] = i_frame[y, x, :3]
        else:
            # If no alpha channel, just overlay as a regular BGR frame
            combined_frame = i_frame

        return combined_frame


class TextAnimator:
    """
    The TextAnimator class creates and manages text animations.
    It supports various effects like blinking, color cycling, explosions, and scrolling.
    The class generates animation frames as numpy arrays, allowing for video export and integration with other display
    methods.

    The class initializes with text, dimensions, speed, color, font, and effect parameters.
    It uses PIL to create text images and OpenCV for image manipulation and effects.
    The generate() method creates animation frames based on the specified direction and speed, applying any chosen effects.
    Helper methods manage specific effects, dynamic text updates, and video export.
    The class also includes pause, resume, and stop functionality
    """
    def __init__(
        self,
        text: str,
        width: int,
        height: int,
        speed: float,
        direction: str,
        color: Tuple[int, int, int],
        fps: int,
        font_path: Optional[str] = None,
        font_size: Optional[int] = None,
        bg_color: Optional[Tuple[int, int, int]] = None,
        opacity: float = 1.0,
        effect: Optional[str] = None,
        alignment: str = "left",
        shadow: bool = False,
        shadow_color: Tuple[int, int, int] = (0, 0, 0),
        shadow_offset: Tuple[int, int] = (2, 2),
        explode_speed: int = 5,  # Speed of the explosion effect
        blink_interval: float = .5,  # Blink interval in seconds
        color_change_interval: int = 1,  # Color change interval in seconds
        explode_pre_delay: float = 0.0  # Delay before explosion in seconds
    ):
        self.text_image = None
        self.effect_params = None
        self.font = None
        self.next_text_change = None
        self.text_index = None
        self.text_interval = None
        self.current_frame = None # This will now store the BGRA text overlay frame
        self.delta_y = None
        self.delta_x = None
        self.y_pos = None
        self.x_pos = None
        self.text = text
        self.width = width
        self.height = height
        self.speed = speed  # Pixels per second
        self.direction = direction.lower()
        self.color = color  # (B, G, R)
        self.fps = fps
        self.font_path = font_path
        self.font_size = font_size or int(height * 0.5)
        self.bg_color = bg_color
        self.opacity = opacity
        self.effect = effect
        self.alignment = alignment.lower()
        self.shadow = shadow
        self.shadow_color = shadow_color
        self.shadow_offset = shadow_offset
        self.explode_speed = explode_speed
        self.blink_interval = blink_interval
        self.color_change_interval = color_change_interval
        self.text_sequence = None  # For dynamic text
        self.explode_pre_delay = explode_pre_delay * fps  # Delay before explosion in frames
        self.particles = [{"position": [np.random.randint(0, self.width), np.random.randint(0, self.height)],
                        "velocity": [np.random.uniform(-1, 1), np.random.uniform(-1, 1)]} for _ in range(50)]
        self.frame_counter = 0  # Added line

        self.apply()
        
        self.paused = False
        self.last_frame_time = time.perf_counter()


    def apply(self):
        """Initializes the font, effect parameters, text image, and scrolling positions.

        This method prepares the TextAnimator for animation by setting up all necessary resources and state.
        It should be called whenever parameters are updated to ensure the animation reflects the latest settings.
        """
        # Initialize font using PIL
        self.init_font()

        # Initialize effect parameters
        self.effect_params = self.init_effect_params()

        # Initialize text image
        text_logger.debug("Initializing TextAnimator")
        self.text_image = self.create_text_image()

        # Initialize scrolling positions based on direction
        self.initialize_scrolling()

    def update_params(self, **kwargs):
        """
        Dynamically updates animator parameters and re-initializes the animation.

        This allows for real-time changes to the text animation by accepting
        any of the constructor's parameters as keyword arguments.

        Args:
            **kwargs: Keyword arguments corresponding to the animator's
                      attributes (e.g., text="New Text", speed=100,
                      effect="explode").
        """
        updated = False
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                text_logger.info(f"Updated TextAnimator parameter '{key}' to '{value}'.")
                updated = True
            else:
                text_logger.warning(f"Attempted to update unknown TextAnimator parameter: '{key}'.")

        if updated:
            # Re-initialize the animator to apply the new settings
            self.apply()
            text_logger.info("TextAnimator re-initialized with new parameters.")

    def init_font(self):
        """Initializes the font.

        Loads a TrueType font if a path is provided, otherwise uses a default font.
        Handles potential font loading errors and logs them.
        """
        # if not font provided, try to see in ini
        if self.font_path is None and cfg_mgr.text_config is not None:
            if cfg_mgr.text_config['font_path'] is not None:
                self.font_path = cfg_mgr.text_config['font_path']
            if cfg_mgr.text_config['font_size'] is not None:
                self.font_path = cfg_mgr.text_config['font_size']

        try:
            if self.font_path:
                self.font = ImageFont.truetype(self.font_path, self.font_size)
            else:
                self.font = ImageFont.load_default(size=self.font_size)
        except Exception as e:
            text_logger.error(f"Failed to load font: {e}")
            self.font = ImageFont.load_default(size=self.font_size)

    def create_text_image(self, text=None, color=None, opacity=None, shadow=None) -> Image.Image:
        """Creates an image of the text with optional effects.

        Allows overriding text, color, opacity, and shadow for generating temporary images
        (e.g., for explode effect).

        Renders the text with specified font, color, and shadow onto a
        transparent image, considering scrolling direction and alignment.
        """

        # Use instance attributes if no overrides provided
        text = text or self.text
        color = color or self.color
        opacity = opacity or self.opacity
        shadow = shadow or self.shadow

        # Calculate text size
        dummy_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Determine canvas size based on direction and text size
        if self.direction in ["left", "right"]:
            canvas_width = text_width + self.width # Ensure enough space for scrolling
            canvas_height = max(self.height, int(text_height))  # ensure canvas height accommodates text
        elif self.direction in ["up", "down"]:
            canvas_width = max(self.width, int(text_width))  # ensure canvas width accommodates text
            canvas_height = text_height + self.height # Ensure enough space for scrolling
        else:
            text_logger.warning(f"Unknown direction '{self.direction}'. Defaulting to 'left'.")
            self.direction = "left"
            canvas_width = text_width + self.width
            canvas_height = max(self.height, int(text_height))

        # Create image with transparency or background color
        if self.bg_color:
            # If bg_color is provided, create a non-transparent background
            text_image = Image.new("RGBA", (canvas_width, canvas_height), self.bg_color + (255,))
        else:
            # Otherwise, create a fully transparent background
            text_image = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

        draw = ImageDraw.Draw(text_image)

        # Calculate text position based on alignment
        x, y = self.calculate_text_position(text_width, text_height, canvas_width, canvas_height)

        # Draw shadow if enabled
        if shadow:
            shadow_x, shadow_y = self.shadow_offset
            draw.text((x + shadow_x, y + shadow_y), text, font=self.font, fill=self.shadow_color + (int(255 * opacity),))

        # Draw text
        draw.text((x, y), text, font=self.font, fill=color + (int(255 * opacity),))

        return text_image

    def calculate_text_position(self, text_width, text_height, canvas_width, canvas_height):
        """Calculates the (x, y) position of the text based on alignment and direction."""
        if self.direction in ["left", "right"]:
            y = (canvas_height - text_height) // 2
            if self.alignment == "center":
                x = (canvas_width - text_width) // 2  # Correct centering calculation
            elif self.alignment == "right":
                x = canvas_width - text_width  # Right-align text
            else:  # left alignment
                x = 0
        elif self.direction in ["up", "down"]:
            x = (canvas_width - text_width) // 2
            if self.alignment == "center":
                y = (canvas_height - text_height) // 2  # Correct centering calculation
            elif self.alignment == "right":  # bottom alignment for vertical scrolling
                y = canvas_height - text_height
            else:  # top alignment
                y = 0
        else:
            x, y = 0, 0  # default position
        return x, y


    def initialize_scrolling(self):
        """Initializes scrolling position and speed."""
        if self.direction == "down":
            self.x_pos = 0
            self.y_pos = -self.text_image.height # Start above the screen
            self.delta_x = 0
            self.delta_y = self.speed / self.fps
        elif self.direction == "right":
            self.x_pos = -self.text_image.width # Start left of the screen
            self.y_pos = 0
            self.delta_x = self.speed / self.fps
            self.delta_y = 0
        elif self.direction == "up":
            self.x_pos = 0
            self.y_pos = self.height # Start below the screen
            self.delta_x = 0
            self.delta_y = -self.speed / self.fps
        else:  # left
            self.x_pos = self.width # Start right of the screen
            self.y_pos = 0
            self.delta_x = -self.speed / self.fps
            self.delta_y = 0


    def init_effect_params(self):
        """Initializes parameters for text effects."""

        params = {}

        if self.effect == "blink":
            params["blink"] = True
            params["blink_interval"] = self.fps * self.blink_interval  # Blink every second
            params["blink_counter"] = 0
            params["visible"] = True
        elif self.effect == "color_cycle":
            params["color_cycle"] = [
                (255, 0, 0),  # Red
                (0, 255, 0),  # Green
                (0, 0, 255),  # Blue
                (255, 255, 0),  # Yellow
                (255, 0, 255),  # Magenta
                (0, 255, 255),  # Cyan
            ]
            params["current_color_index"] = 0
            params["color_change_interval"] = (
                    self.fps * self.color_change_interval
            )  # Change color every 2 seconds
            params["color_change_counter"] = 0
        elif self.effect == "rainbow_cycle":
            params["rainbow_cycle"] = True
            params["rainbow_counter"] = 0
            params["rainbow_step"] = 1  # Adjust for speed of color change
        elif self.effect == "explode":
            params["explode"] = True
            params["explode_start_frame"] = self.fps * 2  # Start explode after 2 seconds (not used with pre_delay)
            params["explode_counter"] = 0
            params["explode_speed"] = self.explode_speed  # Adjust explosion speed
            params["fragments"] = []  # Store exploded fragments
            params["explode_pre_delay_frames"] = int(self.explode_pre_delay)  # pre_delay in frames
        # Add wave effect
        elif self.effect == "wave":
            params["wave_counter"] = 0  # Start the wave effect counter
            params["wave_amplitude"] = 10
            params["wave_frequency"] = 0.1
        # Add shake effect
        elif self.effect == "shake":
            params["shake_counter"] = 0  # Start the shake effect counter
            params["shake_amplitude"] = 5
            params["shake_frequency"] = 0.2
        # Add scale effect
        elif self.effect == "scale":
            params["scale_counter"] = 0  # Start the scale effect counter
            params["scale_amplitude"] = 0.1
            params["scale_frequency"] = 0.1

        return params

    def apply_effects(self):
        """Applies text effects based on the current frame."""

        if not self.effect:
            return

        if self.effect == "blink":
            self.apply_blink_effect()
        elif self.effect == "color_cycle":
            self.apply_color_cycle_effect()
        elif self.effect == "rainbow_cycle":
            self.apply_rainbow_cycle_effect()
        # Explode effect is handled directly in generate() for rendering
        elif self.effect == "shake":
            self.apply_shake_effect()
        elif self.effect == "wave":
            self.apply_wave_effect()
        elif self.effect == "scale":
            self.apply_scale_effect()
        elif self.effect == "particle":
            self.apply_particle_effect() # Note: particle effect modifies the final frame, not self.text_image


    def enable_dynamic_text(self, text_sequence, interval):
        """Enable dynamic text that changes at specified intervals.

        Args:
            text_sequence (list of str): List of text strings to cycle through.
            interval (float): Time interval (in seconds) for switching text.
            animator.enable_dynamic_text(["Hello", "Dynamic Text", "NiceGUI Rocks!"], interval=2.0)
        """
        self.text_sequence = text_sequence
        self.text_interval = interval
        self.text_index = 0
        self.next_text_change = time.perf_counter() + interval

    def update_text(self):
        """Checks if it's time to update the text and switches to the next one."""
        current_time = time.perf_counter()
        if current_time >= self.next_text_change:
            self.text_index = (self.text_index + 1) % len(self.text_sequence)
            self.text = self.text_sequence[self.text_index]
            self.text_image = self.create_text_image()
            self.next_text_change = current_time + self.text_interval


    def apply_blink_effect(self):
        """Applies blink effect."""
        self.effect_params["blink_counter"] += 1
        if self.effect_params["blink_counter"] >= self.effect_params["blink_interval"]:
            self.effect_params["blink_counter"] = 0
            self.effect_params["visible"] = not self.effect_params["visible"]

        if not self.effect_params["visible"]:
            # Create a fully transparent image if not visible
            self.text_image = Image.new("RGBA", self.text_image.size, (0, 0, 0, 0))
        else:
            # Restore text image (re-create to ensure correct state)
            self.text_image = self.create_text_image()

    def apply_color_cycle_effect(self):
        """Applies color cycle effect."""
        self.effect_params["color_change_counter"] += 1
        if self.effect_params["color_change_counter"] >= self.effect_params["color_change_interval"]:
            self.effect_params["color_change_counter"] = 0
            self.effect_params["current_color_index"] = (self.effect_params["current_color_index"] + 1) % len(
                self.effect_params["color_cycle"]
            )
            self.color = self.effect_params["color_cycle"][self.effect_params["current_color_index"]]
            self.text_image = self.create_text_image()  # Update text image with new color

    def apply_rainbow_cycle_effect(self):
        """Applies rainbow cycle effect."""
        self.effect_params["rainbow_counter"] += self.effect_params["rainbow_step"]
        # OpenCV's HSV hue range is 0-179 for 8-bit images
        hue = int(self.effect_params["rainbow_counter"] % 180)
        new_color = tuple(
            int(c)
            for c in cv2.cvtColor(
                np.array([[[hue, 255, 255]]], dtype=np.uint8), cv2.COLOR_HSV2BGR
            )[0][0]
        )
        self.color = new_color
        self.text_image = self.create_text_image()

    def apply_wave_effect(self):
        """Applies wave effect to text position."""
        # Note: This directly modifies x_pos/y_pos, which will be used in rendering
        wave_amplitude = self.effect_params.get("wave_amplitude", 10)
        wave_frequency = self.effect_params.get("wave_frequency", 0.1)
        # Store original y_pos to apply wave on top of scrolling
        if not hasattr(self, '_original_y_pos'):
            self._original_y_pos = self.y_pos
        self.y_pos = self._original_y_pos + wave_amplitude * math.sin(self.effect_params["wave_counter"] * wave_frequency)
        self.effect_params["wave_counter"] += 0.1

    def apply_shake_effect(self):
        """Shakes the text left and right."""
        # Note: This directly modifies x_pos/y_pos, which will be used in rendering
        shake_amplitude = self.effect_params.get("shake_amplitude", 5)
        shake_frequency = self.effect_params.get("shake_frequency", 0.2)
        # Store original x_pos to apply shake on top of scrolling
        if not hasattr(self, '_original_x_pos'):
            self._original_x_pos = self.x_pos
        self.x_pos = self._original_x_pos + shake_amplitude * math.sin(self.effect_params["shake_counter"] * shake_frequency)
        self.effect_params["shake_counter"] += 0.1


    def apply_scale_effect(self):
        """Applies the scale effect to the text image."""
        # This effect needs to re-create the text_image with a new size
        scale_amplitude = self.effect_params.get("scale_amplitude", 0.1)
        scale_frequency = self.effect_params.get("scale_frequency", 0.1)

        scale_factor = 1 + scale_amplitude * math.sin(scale_frequency * self.frame_counter)
        
        # Ensure scale factor is positive
        scale_factor = max(0.1, scale_factor) 

        new_font_size = int(self.font_size * scale_factor)
        if new_font_size <= 0: # Avoid zero or negative font size
            new_font_size = 1
        
        # Re-initialize font with new size
        try:
            if self.font_path:
                self.font = ImageFont.truetype(self.font_path, new_font_size)
            else:
                self.font = ImageFont.load_default(size=new_font_size)
        except Exception as e:
            text_logger.error(f"Failed to load font with new size {new_font_size}: {e}")
            self.font = ImageFont.load_default(size=self.font_size) # Fallback to original size

        # Re-create text image with new font size
        self.text_image = self.create_text_image()


    def apply_particle_effect(self):
        """Adds particles around the text for a sparkly effect."""
        # This effect will be applied directly to the final composite frame in generate()
        pass # The logic will be moved to generate() or a new rendering step

    def apply_explode_effect(self):
        """Applies explode effect after a delay."""

        if self.effect_params["explode_counter"] == self.effect_params["explode_pre_delay_frames"]:
            self.explode_text()  # Explode after the pre-delay
            # After explosion, the original text_image should be transparent
            self.text_image = Image.new("RGBA", self.text_image.size, (0, 0, 0, 0))

        if self.effect_params["explode_counter"] >= self.effect_params["explode_pre_delay_frames"]:
            self.update_exploding_fragments()  # Update fragment positions only after pre-delay

        self.effect_params["explode_counter"] += 1

    def explode_text(self):
        """Splits text into fragments for explosion effect, adjusting for alignment."""
        self.effect_params["fragments"] = []
        # Create a temporary image of the text for fragmentation
        image = self.create_text_image(text=self.text, color=self.color, opacity=self.opacity, shadow=self.shadow)
        image_width, image_height = image.size
        
        # Calculate average character width for fragmentation
        # This is a simplification; for precise fragmentation, each char's bbox would be needed.
        if len(self.text) > 0:
            char_width = image_width // len(self.text)
        else:
            char_width = image_width # If no text, treat whole image as one fragment

        # Determine the starting X position for the text within its own image
        # This is important for correctly cropping fragments if the text image has padding
        dummy_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        bbox = draw.textbbox((0, 0), self.text, font=self.font)
        actual_text_start_x_in_image = bbox[0]
        actual_text_width = bbox[2] - bbox[0]

        # Adjust char_width based on actual text width
        if len(self.text) > 0:
            char_width = actual_text_width // len(self.text)
        else:
            char_width = actual_text_width

        for i, char in enumerate(self.text):
            # Calculate fragment boundaries within the text_image
            # We need to crop from the text_image, not the full canvas
            fragment_left_in_image = actual_text_start_x_in_image + (i * char_width)
            fragment_right_in_image = actual_text_start_x_in_image + ((i + 1) * char_width)
            
            # Ensure boundaries are within the image
            fragment_left_in_image = max(0, fragment_left_in_image)
            fragment_right_in_image = min(image_width, fragment_right_in_image)

            if fragment_left_in_image >= fragment_right_in_image:
                continue # Skip if fragment is empty

            char_image = image.crop((fragment_left_in_image, 0, fragment_right_in_image, image_height))
            
            # Initial position of the fragment on the main canvas (self.width, self.height)
            # This is where the character would have been before explosion
            initial_x_on_canvas = self.x_pos + fragment_left_in_image
            initial_y_on_canvas = self.y_pos # Assuming text is vertically centered or at y_pos

            self.effect_params["fragments"].append(
                {
                    "image": char_image, # PIL Image (RGBA)
                    "position": [float(initial_x_on_canvas), float(initial_y_on_canvas)], # Use float for sub-pixel movement
                    "velocity": [
                        np.random.uniform(-self.effect_params["explode_speed"], self.effect_params["explode_speed"]),
                        np.random.uniform(-self.effect_params["explode_speed"] * 2,
                                          self.effect_params["explode_speed"]),
                    ],
                }
            )

    def update_exploding_fragments(self):
        """Updates the position of exploding fragments."""

        for fragment in self.effect_params["fragments"]:
            fragment["position"][0] += fragment["velocity"][0]
            fragment["position"][1] += fragment["velocity"][1]
            fragment["velocity"][1] += 0.5  # Gravity

    def generate(self) -> Optional[np.ndarray]:
        """Generates the next frame of the animation as a BGRA NumPy array.

        Returns:
            The next frame of the animation as a BGRA NumPy array (height, width, 4),
            or None if the animation is paused.
        """

        if self.paused:
            return self.current_frame # Return last rendered frame if paused

        current_time = time.perf_counter()
        elapsed_time = current_time - self.last_frame_time

        self.frame_counter += 1

        # Only update state if enough time has passed for a new frame
        if elapsed_time >= 1.0 / self.fps:
            self.last_frame_time = current_time

            if self.text_sequence:
                self.update_text()

            # Reset original positions for wave/shake effects before applying scrolling
            if hasattr(self, '_original_x_pos'):
                self.x_pos = self._original_x_pos
            if hasattr(self, '_original_y_pos'):
                self.y_pos = self._original_y_pos

            if self.direction in ["left", "right"]:
                self.x_pos += self.delta_x
                # Loop scrolling
                if self.direction == "left" and self.x_pos <= -self.text_image.width:
                    self.x_pos = self.width
                elif self.direction == "right" and self.x_pos >= self.width:
                    self.x_pos = -self.text_image.width
            elif self.direction in ["up", "down"]:
                self.y_pos += self.delta_y
                # Loop scrolling
                if self.direction == "up" and self.y_pos <= -self.text_image.height:
                    self.y_pos = self.height
                elif self.direction == "down" and self.y_pos >= self.height:
                    self.y_pos = -self.text_image.height
            
            # Apply effects that modify position or text_image
            self.apply_effects()

        # --- Rendering the current frame state ---
        output_frame_bgra = np.zeros((self.height, self.width, 4), dtype=np.uint8) # Transparent BGRA canvas

        if self.effect == "explode":
            # Handle explosion rendering
            if self.effect_params["explode_counter"] <= self.effect_params["explode_pre_delay_frames"]:
                # Before explosion, render the original text_image
                text_to_render_pil = self.text_image
                x_offset = int(self.x_pos)
                y_offset = int(self.y_pos)
            else:
                # After explosion, render fragments
                for fragment in self.effect_params["fragments"]:
                    frag_img_pil = fragment["image"] # This is RGBA PIL Image
                    frag_np_bgra = cv2.cvtColor(np.array(frag_img_pil), cv2.COLOR_RGBA2BGRA)
                    
                    fx = int(fragment["position"][0])
                    fy = int(fragment["position"][1])
                    fw, fh = frag_np_bgra.shape[1], frag_np_bgra.shape[0]

                    # Calculate region to paste fragment onto output_frame_bgra
                    x1 = max(0, fx)
                    y1 = max(0, fy)
                    x2 = min(self.width, fx + fw)
                    y2 = min(self.height, fy + fh)

                    if x1 < x2 and y1 < y2:
                        # Calculate corresponding region in fragment image
                        frag_x1 = x1 - fx
                        frag_y1 = y1 - fy
                        frag_x2 = x2 - fx
                        frag_y2 = y2 - fy

                        # Extract alpha channel from fragment
                        alpha_frag = frag_np_bgra[frag_y1:frag_y2, frag_x1:frag_x2, 3] / 255.0
                        alpha_frag_3_channel = cv2.merge([alpha_frag, alpha_frag, alpha_frag])

                        # Extract BGR from fragment
                        bgr_frag = frag_np_bgra[frag_y1:frag_y2, frag_x1:frag_x2, :3]

                        # Extract background BGR from output_frame_bgra
                        bgr_bg = output_frame_bgra[y1:y2, x1:x2, :3]

                        # Blend BGR channels
                        output_frame_bgra[y1:y2, x1:x2, :3] = (bgr_bg * (1 - alpha_frag_3_channel) + bgr_frag * alpha_frag_3_channel).astype(np.uint8)
                        # Set alpha channel of output_frame_bgra to max of current alpha and fragment alpha
                        output_frame_bgra[y1:y2, x1:x2, 3] = np.maximum(output_frame_bgra[y1:y2, x1:x2, 3], frag_np_bgra[frag_y1:frag_y2, frag_x1:frag_x2, 3])
                
                # No need to render text_to_render_pil if fragments are being rendered
                text_to_render_pil = None # Ensure it's not rendered again below
                x_offset = 0
                y_offset = 0

            if text_to_render_pil:
                text_np_bgra = cv2.cvtColor(np.array(text_to_render_pil), cv2.COLOR_RGBA2BGRA)
                
                # Calculate region to paste text onto output_frame_bgra
                x1 = max(0, x_offset)
                y1 = max(0, y_offset)
                x2 = min(self.width, x_offset + text_np_bgra.shape[1])
                y2 = min(self.height, y_offset + text_np_bgra.shape[0])

                if x1 < x2 and y1 < y2:
                    # Calculate corresponding region in text image
                    text_x1 = x1 - x_offset
                    text_y1 = y1 - y_offset
                    text_x2 = x2 - x_offset
                    text_y2 = y2 - y_offset

                    # Extract alpha channel from text
                    alpha_text = text_np_bgra[text_y1:text_y2, text_x1:text_x2, 3] / 255.0
                    alpha_text_3_channel = cv2.merge([alpha_text, alpha_text, alpha_text])

                    # Extract BGR from text
                    bgr_text = text_np_bgra[text_y1:text_y2, text_x1:text_x2, :3]

                    # Extract background BGR from output_frame_bgra
                    bgr_bg = output_frame_bgra[y1:y2, x1:x2, :3]

                    # Blend BGR channels
                    output_frame_bgra[y1:y2, x1:x2, :3] = (bgr_bg * (1 - alpha_text_3_channel) + bgr_text * alpha_text_3_channel).astype(np.uint8)
                    # Set alpha channel of output_frame_bgra to max of current alpha and text alpha
                    output_frame_bgra[y1:y2, x1:x2, 3] = np.maximum(output_frame_bgra[y1:y2, x1:x2, 3], text_np_bgra[text_y1:text_y2, text_x1:text_x2, 3])
        else: # No explode effect
            text_np_bgra = cv2.cvtColor(np.array(self.text_image), cv2.COLOR_RGBA2BGRA)
            x_offset = int(self.x_pos)
            y_offset = int(self.y_pos)

            # Calculate region to paste text onto output_frame_bgra
            x1 = max(0, x_offset)
            y1 = max(0, y_offset)
            x2 = min(self.width, x_offset + text_np_bgra.shape[1])
            y2 = min(self.height, y_offset + text_np_bgra.shape[0])

            if x1 < x2 and y1 < y2:
                # Calculate corresponding region in text image
                text_x1 = x1 - x_offset
                text_y1 = y1 - y_offset
                text_x2 = x2 - x_offset
                text_y2 = y2 - y_offset

                # Extract alpha channel from text
                alpha_text = text_np_bgra[text_y1:text_y2, text_x1:text_x2, 3] / 255.0
                alpha_text_3_channel = cv2.merge([alpha_text, alpha_text, alpha_text])

                # Extract BGR from text
                bgr_text = text_np_bgra[text_y1:text_y2, text_x1:text_x2, :3]

                # Extract background BGR from output_frame_bgra
                bgr_bg = output_frame_bgra[y1:y2, x1:x2, :3]

                # Blend BGR channels
                output_frame_bgra[y1:y2, x1:x2, :3] = (bgr_bg * (1 - alpha_text_3_channel) + bgr_text * alpha_text_3_channel).astype(np.uint8)
                # Set alpha channel of output_frame_bgra to max of current alpha and text alpha
                output_frame_bgra[y1:y2, x1:x2, 3] = np.maximum(output_frame_bgra[y1:y2, x1:x2, 3], text_np_bgra[text_y1:text_y2, text_x1:text_x2, 3])

        # Apply particle effect if enabled (modifies the output_frame_bgra directly)
        if self.effect == "particle":
            # Convert BGRA to BGR for particle drawing, then back to BGRA
            bgr_for_particles = cv2.cvtColor(output_frame_bgra, cv2.COLOR_BGRA2BGR)
            for particle in self.particles:
                particle["position"][0] += particle["velocity"][0]
                particle["position"][1] += particle["velocity"][1]
                if not (0 <= particle["position"][0] < self.width) or not (0 <= particle["position"][1] < self.height):
                    particle["position"] = [np.random.randint(0, self.width), np.random.randint(0, self.height)]
                cv2.circle(bgr_for_particles, (int(particle["position"][0]), int(particle["position"][1])), 2,
                           (255, 255, 255), -1) # White particles
            output_frame_bgra = cv2.cvtColor(bgr_for_particles, cv2.COLOR_BGR2BGRA)


        self.current_frame = output_frame_bgra # Store the last rendered frame
        return output_frame_bgra


    def export_as_video(self, output_file, duration=10):
        """Exports the animation as a video file."""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        # VideoWriter expects BGR, so convert BGRA to BGR before writing
        out = cv2.VideoWriter(output_file, fourcc, self.fps, (self.width, self.height))

        frame_count = int(duration * self.fps)
        for _ in range(frame_count):
            frame_bgra = self.generate()
            if frame_bgra is not None:
                frame_bgr = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
                out.write(frame_bgr)

        out.release()
        text_logger.info(f"Video saved to {output_file}")

    def pause(self):
        """Pauses the animation."""

        self.paused = True

    def resume(self):
        """Resumes the animation."""

        self.paused = False
        self.last_frame_time = time.perf_counter()

    def stop(self):
        """Stops the animator."""

        text_logger.debug("Stopping TextAnimator")
