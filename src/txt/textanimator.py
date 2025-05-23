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
        self.current_frame = None
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
        # Initialize font using PIL
        self.init_font()

        # Initialize effect parameters
        self.effect_params = self.init_effect_params()

        # Initialize text image
        text_logger.debug("Initializing TextAnimator")
        self.text_image = self.create_text_image()

        # Initialize scrolling positions based on direction
        self.initialize_scrolling()


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
            canvas_width = text_width + self.width
            canvas_height = max(self.height, int(text_height))  # ensure canvas height accommodates text
        elif self.direction in ["up", "down"]:
            canvas_width = max(self.width, int(text_width))  # ensure canvas width accommodates text
            canvas_height = text_height + self.height
        else:
            text_logger.warning(f"Unknown direction '{self.direction}'. Defaulting to 'left'.")
            self.direction = "left"
            canvas_width = text_width + self.width
            canvas_height = max(self.height, int(text_height))

        # Create image with transparency or background color
        if self.bg_color:
            text_image = Image.new("RGBA", (canvas_width, canvas_height), self.bg_color + (255,))
        else:
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
            self.y_pos = -self.text_image.height
            self.delta_x = 0
            self.delta_y = self.speed / self.fps
        elif self.direction == "right":
            self.x_pos = -self.text_image.width
            self.y_pos = 0
            self.delta_x = self.speed / self.fps
            self.delta_y = 0
        elif self.direction == "up":
            self.x_pos = 0
            self.y_pos = self.height
            self.delta_x = 0
            self.delta_y = -self.speed / self.fps
        else:  # left
            self.x_pos = self.width
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
            params["explode_start_frame"] = self.fps * 2  # Start explode after 2 seconds
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
        elif self.effect == "explode":
            self.apply_explode_effect()
        elif self.effect == "shake":
            self.apply_shake_effect()
        elif self.effect == "wave":
            self.apply_wave_effect()
        elif self.effect == "scale":
            self.apply_scale_effect()
        elif self.effect == "particle":
            self.apply_particle_effect()


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
            self.text_image = Image.new("RGBA", self.text_image.size, (0, 0, 0, 0))  # Make text transparent
        else:
            self.text_image = self.create_text_image()  # Restore text

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
        hue = int(self.effect_params["rainbow_counter"] % 360)
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
        wave_amplitude = 10  # Adjust the wave height
        wave_frequency = 2  # Adjust the wave speed
        self.y_pos = self.y_pos + wave_amplitude * math.sin(self.effect_params["wave_counter"] * wave_frequency)
        self.effect_params["wave_counter"] += 0.1

    def apply_shake_effect(self):
        """Shakes the text left and right."""
        shake_amplitude = 5  # Adjust the shake amplitude
        shake_frequency = 10  # Adjust how often it shakes
        self.x_pos += shake_amplitude * math.sin(self.effect_params["shake_counter"] * shake_frequency)
        self.effect_params["shake_counter"] += 0.1


    def apply_scale_effect(self):
        """Applies the scale effect to the text image."""
        if self.effect == "scale":
            scale_factor = 1 + self.effect_params["scale_amplitude"] * math.sin(
                self.effect_params["scale_frequency"] * self.frame_counter
            )
            new_width = int(self.width * scale_factor)
            new_height = int(self.height * scale_factor)

            # Replace Image.ANTIALIAS with Image.Resampling.LANCZOS
            resized_image = self.text_image.resize(
                (new_width, new_height),
                Image.Resampling.BICUBIC  # Use LANCZOS for antialiasing
            )

            self.text_image = resized_image


    def apply_particle_effect(self):
        """Adds particles around the text for a sparkly effect."""

        for particle in self.particles:
            particle["position"][0] += particle["velocity"][0]
            particle["position"][1] += particle["velocity"][1]
            if not (0 <= particle["position"][0] < self.width) or not (0 <= particle["position"][1] < self.height):
                particle["position"] = [np.random.randint(0, self.width), np.random.randint(0, self.height)]

            cv2.circle(self.current_frame, (int(particle["position"][0]), int(particle["position"][1])), 2,
                       (255, 255, 255), -1)

    def apply_explode_effect(self):
        """Applies explode effect after a delay."""

        if self.effect_params["explode_counter"] == self.effect_params["explode_pre_delay_frames"]:
            self.explode_text()  # Explode after the pre-delay

        if self.effect_params["explode_counter"] >= self.effect_params["explode_pre_delay_frames"]:
            self.update_exploding_fragments()  # Update fragment positions only after pre-delay

        self.effect_params["explode_counter"] += 1

    def explode_text(self):
        """Splits text into fragments for explosion effect, adjusting for alignment."""
        self.effect_params["fragments"] = []
        image = self.create_text_image(text=self.text, color=self.color, opacity=self.opacity, shadow=self.shadow)
        image_width, image_height = image.size
        char_width = image_width // len(self.text)

        if self.alignment == "right":
            start_x = self.width - image_width
        elif self.alignment == "center":
            start_x = (self.width - image_width) // 2
        else:
            start_x = 0

        top = 0
        for i, char in enumerate(self.text):
            left = start_x + (i * char_width)
            right = start_x + ((i + 1) * char_width)
            bottom = image_height

            char_image = image.crop((left - start_x, top, right - start_x, bottom))
            self.effect_params["fragments"].append(
                {
                    "image": char_image,
                    "position": [left, top],
                    "velocity": [
                        np.random.uniform(-self.effect_params["explode_speed"], self.effect_params["explode_speed"]),
                        np.random.uniform(-self.effect_params["explode_speed"] * 2,
                                          self.effect_params["explode_speed"]),
                    ],
                }
            )

        # Make original text transparent after fragments are created
        self.text_image = Image.new("RGBA", self.text_image.size, (0, 0, 0, 0))

    def update_exploding_fragments(self):
        """Updates the position of exploding fragments."""

        for fragment in self.effect_params["fragments"]:
            fragment["position"][0] += fragment["velocity"][0]
            fragment["position"][1] += fragment["velocity"][1]
            fragment["velocity"][1] += 0.5  # Gravity

    def generate(self) -> Optional[np.ndarray]:
        """Generates the next frame of the animation.

        Returns:
            The next frame of the animation as a NumPy array, or None if the
            animation is paused or no new frame is generated.
        """

        if self.paused:
            return self.current_frame

        current_time = time.perf_counter()
        elapsed_time = current_time - self.last_frame_time

        self.frame_counter += 1  # Added line

        if elapsed_time >= 1.0 / self.fps:
            self.last_frame_time = current_time
            if self.text_sequence:
                self.update_text()
            if self.direction in ["left", "right"]:
                self.x_pos += self.delta_x

                if self.direction == "left" and self.x_pos <= -self.text_image.width:
                    self.x_pos = self.width
                elif self.direction == "right" and self.x_pos >= self.width:
                    self.x_pos = -self.text_image.width
            elif self.direction in ["up", "down"]:
                self.y_pos += self.delta_y

                if self.direction == "up" and self.y_pos <= -self.text_image.height:
                    self.y_pos = self.height
                elif self.direction == "down" and self.y_pos >= self.height:
                    self.y_pos = -self.text_image.height

        self.apply_effects()

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        if self.effect == "explode":
            return self.generate_explode(frame)

        frame_pil = self.text_image.copy()
        frame_cv = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGBA2BGRA)
        x = int(self.x_pos)
        y = int(self.y_pos)
        overlay = np.zeros((self.height, self.width, 4), dtype=np.uint8)  # BGRA

        x_start = max(0, x)
        y_start = max(0, y)
        x_end = min(self.width, x + frame_cv.shape[1])
        y_end = min(self.height, y + frame_cv.shape[0])

        text_x_start = max(0, -x)
        text_y_start = max(0, -y)
        text_x_end = text_x_start + (x_end - x_start)
        text_y_end = text_y_start + (y_end - y_start)

        if x_start < x_end and y_start < y_end:
            try:
                overlay[y_start:y_end, x_start:x_end] = frame_cv[text_y_start:text_y_end, text_x_start:text_x_end]
            except ValueError as e:
                # Handle potential shape mismatch during scrolling/exploding transitions
                text_logger.error(f"ValueError during overlay: {e}")
                return self.current_frame # Return last valid frame to avoid crash

        frame_bgra = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)

        return self.add_text_to_bg(frame_bgra, overlay)


    def generate_explode(self, frame):
        """Generates a frame for the explosion effect.

        Creates and positions fragments of the exploded text, handling pre-delay and image conversions.
        """
        if self.effect_params["explode_counter"] <= self.effect_params["explode_pre_delay_frames"]:
            # Display the original text image before explosion
            frame_pil = self.create_text_image(text=self.text, color=self.color, opacity=self.opacity, shadow=self.shadow)
        else:
            frame_pil = Image.new("RGBA", (self.width, self.height))
            for fragment in self.effect_params["fragments"]:
                frame_pil.paste(fragment["image"], (int(fragment["position"][0]), int(fragment["position"][1])), fragment["image"])
        frame_cv = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGBA2BGRA)
        frame_bgra = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)

        # Resize if necessary before adding
        frame_cv = cv2.resize(frame_cv, (self.width, self.height))
        frame_bgra = cv2.resize(frame_bgra, (self.width, self.height))

        # Ensure 4 channels for both images
        if frame_cv.shape[2] == 3:
            frame_cv = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2BGRA)
        if frame_bgra.shape[2] == 3:
            frame_bgra = cv2.cvtColor(frame_bgra, cv2.COLOR_BGR2BGRA)

        return self.add_text_to_bg(frame_bgra, frame_cv)


    def add_text_to_bg(self, text_frame, overlay):
        """Combines the text image with the background frame.

        Adds the text image to the background frame and converts the result to BGR format.
        """
        combined = cv2.add(text_frame, overlay)
        final_frame = cv2.cvtColor(combined, cv2.COLOR_BGRA2BGR)
        self.current_frame = final_frame

        return final_frame

    def export_as_video(self, output_file, duration=10):
        """Exports the animation as a video file."""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_file, fourcc, self.fps, (self.width, self.height))

        frame_count = int(duration * self.fps)
        for _ in range(frame_count):
            frame = self.generate()
            out.write(frame)

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
