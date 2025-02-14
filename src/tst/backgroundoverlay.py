import cv2
import numpy as np
from PIL import Image


class BackgroundOverlay:
    def __init__(self, background_path):
        # Load and prepare the tiled background
        self.background_image = Image.open(background_path).convert("RGBA")
        self.bg_np = np.array(self.background_image)
        bgr = self.bg_np[..., :3]
        alpha = self.bg_np[..., 3]
        bg_alpha_scaled = alpha[:, :, np.newaxis] / 255.0
        self.background = (bgr * bg_alpha_scaled + 255 * (1 - bg_alpha_scaled)).astype(np.uint8)

    def get_tiled_background(self, window_width, window_height):
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


# Example Usage:
if __name__ == "__main__":
    # Initialize the background overlay with a tiled image
    bg_overlay = BackgroundOverlay("../../assets/transparency_blocks.png")

    # Load your frame (image to overlay)
    frame = cv2.imread("../../splash-screen.png", cv2.IMREAD_UNCHANGED)  # Ensure it has transparency (RGBA)

    # Apply the background to the frame
    output_frame = bg_overlay.apply_background(frame)

    # Display the result
    cv2.imshow("Frame with Background", output_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
