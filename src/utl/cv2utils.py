"""
 a: zak-45
 d: 06/11/2025
 v: 1.1.0

 Overview:
 This file defines the `CV2Utils` and `ImageUtils` classes, which provide a comprehensive suite of static utility
 functions for image and video processing, preview display, and inter-process communication within the WLEDVideoSync
 application. It leverages the OpenCV (cv2) library for high-performance image manipulation and the Pillow (PIL)
 library for image format handling.

 These utilities are fundamental for handling all visual data, from capturing frames and applying filters to
 displaying real-time previews and preparing images for network transmission.

 Key Architectural Components:

 1.  CV2Utils Class:
     -   **Purpose**: To centralize all OpenCV-related operations, ensuring consistency and reusability across the
         application.
     -   **Image Manipulation**: Includes methods for resizing images (`resize_image`, `resize_keep_aspect_ratio`),
         applying pixel art effects (`pixelart_image`), and overlaying transparent images (`overlay_bgra_on_bgr`).
     -   **Preview Display**: Manages the creation and control of OpenCV preview windows (`cv2_display_frame`,
         `cv2_win_close`, `window_exists`). It also handles cross-platform complexities by supporting separate
         processes for preview windows on non-Windows systems (`sl_main_preview`).
     -   **Inter-Process Communication (IPC)**: Provides utilities for working with `multiprocessing.shared_memory.ShareableList`
         (`send_to_queue`, `frame_add_one`, `frame_remove_one`), enabling efficient sharing of image data between
         different processes or threads.
     -   **Video/GIF Processing**: Offers methods for converting videos to GIFs (`video_to_gif`), resizing GIFs,
         and extracting video metadata (`get_media_info`).
     -   **File Operations**: Includes functionality to save images from buffers (`save_image`).

 2.  ImageUtils Class:
     -   **Purpose**: To provide additional image processing and utility functions, often complementing `CV2Utils`.
     -   **Format Conversion**: Converts NumPy arrays to Base64 strings (`image_array_to_base64`) for web display.
     -   **Filters and Effects**: Applies various image filters such as saturation, brightness, contrast, sharpen,
         and color balance (`process_filters_image`, `apply_filters_cv2`, `filter_balance`, `filter_saturation`, etc.).
     -   **Artistic Effects**: Converts images to ASCII art (`image_to_ascii`).
     -   **Visual Aids**: Draws grids and cell numbers on images (`grid_on_image`).
     -   **Enhancements**: Provides automatic brightness and contrast adjustment (`automatic_brightness_and_contrast`)
         and gamma correction (`gamma_correct_frame`).

3.  VideoThumbnailExtractor Class:
     -   **Purpose**: To extract thumbnail images from video or image files.
     -   **Media Type Detection**: Intelligently determines if a given path points to an image or video file.
     -   **Thumbnail Generation**: Extracts frames at specified time intervals from videos or resizes images to create
         thumbnails (`extract_thumbnails`, `extract_thumbnails_from_video`, `extract_thumbnails_from_image`).
     -   **Error Handling**: Generates blank frames for invalid media files, ensuring robust operation.

 Design Philosophy:
 -   **Static Utilities**: Most functions are static methods, making them easily accessible without needing to
     instantiate the classes. This promotes a functional programming style for image processing tasks.
 -   **Modularity**: Functions are grouped logically into `CV2Utils` (OpenCV-centric), `ImageUtils` (general image
     processing), and `VideoThumbnailExtractor` (media-specific extraction), enhancing code organization.
 -   **Performance**: Leverages OpenCV's optimized C++ backend for fast image processing operations.
 -   **Cross-Platform Compatibility**: Designed with considerations for different operating systems, especially
     regarding preview window management.

"""

import asyncio
import ast
import time
import collections

import cv2
from multiprocessing.shared_memory import ShareableList
import numpy as np
from PIL import Image
import io
import base64
import contextlib
import os
from datetime import datetime
from str2bool import str2bool

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.cv2utils')
cv2utils_logger = logger_manager.logger

class CV2Utils:
    """Provides utility functions for OpenCV (cv2) operations.

    This class offers static methods for image processing, preview display,
    video thumbnail extraction, and other cv2-related tasks.  It also
    includes utilities for handling shared memory lists used for
    inter-process communication.
    """
    def __init__(self):
        pass

    @staticmethod
    def create_grid_from_images(images: list, grid_cols: int = None, gap: int = 2, names: list = None) -> np.ndarray:
        """
        Arranges a list of images into a single grid image.

        Args:
            images (list): A list of images as NumPy arrays (BGR or BGRA).
            grid_cols (int, optional): The number of columns in the grid.
                                       If None, it will be calculated to create a squarish layout.
            gap (int, optional): The size of the gap in pixels between images. Defaults to 2.
            names (list, optional): A list of names to overlay on each image. Must match the length of `images`.

        Returns:
            np.ndarray: A single image representing the grid of input images.
        """
        if not images:
            try:
                # Load the default placeholder image if no images are provided
                default_img_path = cfg_mgr.app_root_path('assets/Source-intro.png')
                default_img = cv2.imread(default_img_path)
                if default_img is not None:
                    return cv2.resize(default_img, (400, 225)) # Resize to a reasonable placeholder size
            except Exception as e:
                cv2utils_logger.warning(f"Could not load default grid image: {e}")
            # Fallback to a blank image if the default image can't be loaded
            return np.zeros((100, 400, 3), dtype=np.uint8)

        # Determine grid dimensions
        num_images = len(images)
        if grid_cols is None:
            grid_cols = int(np.ceil(np.sqrt(num_images)))
        grid_rows = int(np.ceil(num_images / grid_cols))

        # Use fixed preview dimensions from the configuration
        preview_h = int(cfg_mgr.app_config.get('grid_preview_height', 90))
        preview_w = int(cfg_mgr.app_config.get('grid_preview_width', 160))

        # Calculate the total size of the grid canvas, including gaps
        grid_height = grid_rows * preview_h + (grid_rows + 1) * gap
        grid_width = grid_cols * preview_w + (grid_cols + 1) * gap

        # Create the canvas for the grid
        try:
            # Load the background image and resize it to the full grid dimensions
            bg_img_path = cfg_mgr.app_root_path('assets/Source-intro.png')
            grid_image = cv2.imread(bg_img_path)
            if grid_image is None:
                raise FileNotFoundError("Background image could not be loaded.")
            grid_image = cv2.resize(grid_image, (grid_width, grid_height))
        except Exception as e:
            cv2utils_logger.warning(f"Could not load background for grid, falling back to black: {e}")
            # Fallback to a black canvas if the image can't be loaded
            grid_image = np.zeros((grid_height, grid_width, 3), dtype=np.uint8)

        # Place each image into the grid
        for i, img in enumerate(images):
            row = i // grid_cols
            col = i % grid_cols

            # Standardize image size and format
            if img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            resized_img = cv2.resize(img, (preview_w, preview_h))

            # Overlay the name if provided
            if names and i < len(names):
                name_text = names[i]
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.3
                font_thickness = 1
                max_text_width = resized_img.shape[1] - 10  # 5px padding on each side

                # Truncate text if it's too long to fit in the image
                while cv2.getTextSize(name_text, font, font_scale, font_thickness)[0][0] > max_text_width:
                    name_text = name_text[:-1]
                if len(name_text) < len(names[i]):
                    name_text = f'{name_text[:-2]}...'

                text_size = cv2.getTextSize(name_text, font, font_scale, font_thickness)[0] # Recalculate size
                text_x = (resized_img.shape[1] - text_size[0]) // 2
                text_y = resized_img.shape[0] - 10  # 10 pixels from the bottom
                cv2.putText(resized_img, name_text, (text_x, text_y), font, font_scale, (0, 0, 0), font_thickness + 2,
                           cv2.LINE_AA)  # Black outline
                cv2.putText(resized_img, name_text, (text_x, text_y), font, font_scale, (255, 255, 255), font_thickness,
                            cv2.LINE_AA)  # White text

            # Calculate position with gap and paste the image
            y_offset = (row + 1) * gap + row * preview_h
            x_offset = (col + 1) * gap + col * preview_w
            grid_image[y_offset:y_offset + preview_h, x_offset:x_offset + preview_w] = resized_img

        return grid_image

    @staticmethod
    def overlay_bgra_on_bgr(background_bgr, overlay_bgra):
        """
        Overlays a BGRA image with transparency onto a BGR image using vectorized operations.
        """
        h, w = background_bgr.shape[:2]

        # Resize overlay to match background if needed
        if overlay_bgra.shape[:2] != (h, w):
            overlay_bgra = cv2.resize(overlay_bgra, (w, h))

        # Extract the alpha mask of the BGRA overlay and create a 3-channel version
        alpha = overlay_bgra[:, :, 3] / 255.0
        alpha_3 = np.stack([alpha, alpha, alpha], axis=-1)

        # Extract the BGR channels of the overlay
        overlay_bgr = overlay_bgra[:, :, :3]

        # Blend the background and overlay
        composite = (overlay_bgr * alpha_3 + background_bgr * (1 - alpha_3)).astype(np.uint8)

        return composite

    @staticmethod
    def update_sl_with_frame(frame, sl, w, h):
        """Resizes a frame and places it into a shared memory list for inter-process communication.
        This SL is used by the 'SharedList' feature of desktop cast.

        This method resizes the input frame to the specified width and height,applies a workaround for ShareableList
        to ensure proper compatibility, and stores the processed frame and a timestamp in the provided shared list.

        Args:
            frame (np.ndarray): The image frame to be sent.
            sl (ShareableList): The shared memory list to store the frame and timestamp.
            w (int): The target width for resizing the frame.
            h (int): The target height for resizing the frame.

        Returns:
            None
        """

        try:
            frame = CV2Utils.resize_image(frame, w, h, keep_ratio=False)
            frame = CV2Utils.frame_add_one(frame)

            sl[0] = frame
            sl[1] = time.time()

        except Exception as e:
            cv2utils_logger.error(f'Error to set frame in SL : {str(e)}')

    @staticmethod
    def frame_add_one(frame):
        """Appends a non-zero byte to a frame's byte representation.

        This workaround addresses a ShareableList bug where zero-sized byte strings cause issues.  It converts the
        NumPy array representing the frame to bytes, appends a non-zero byte, and returns the modified bytes.
        see https://github.com/python/cpython/issues/106939
        """
        frame = frame.tobytes()
        frame = bytearray(frame)
        frame.append(1)
        return bytes(frame)

    @staticmethod
    def frame_remove_one(frame):
        """Removes the last byte from a frame's byte representation.

        This function reverses the workaround applied by frame_add_1, removing the extra byte appended to handle a
        ShareableList bug.  It converts the byte string to a bytearray, removes the last byte, and returns the
        modified byte string.
        """
        # remove the last byte
        frame = bytearray(frame)
        frame = frame[:-1]
        return bytes(frame)


    @staticmethod
    def set_black_bg(image):
        """
        put black background to an image with transparency

        # Load the image
        image_path = '/mnt/data/0 11-10-13-3313.png'
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)

        """

        # Ensure the image has an alpha channel (transparency)
        if image.shape[2] == 4:
            # Split the image into its channels
            b, g, r, a = cv2.split(image)
            # Create a black background
            black_background = np.zeros_like(b)
            # Use the alpha channel as a mask to combine the black background with the image
            image_with_black_bg = cv2.merge((b, g, r, a))
            image_with_black_bg[:, :, :3] = np.where(a[:, :, np.newaxis] == 0, black_background[:, :, np.newaxis],
                                                     image_with_black_bg[:, :, :3])
        else:
            # If no alpha channel, just read the image as is
            image_with_black_bg = image

        return image_with_black_bg

    @staticmethod
    def window_exists(win_name):
        """Returns True if the window exists, False otherwise"""
        try:
            return cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) > 0
        except cv2.error:
            return False

    @staticmethod
    def cv2_win_close(server_port, class_name, t_name, t_viinput):
        """ Close cv2 window created by imshow """

        cv2utils_logger.debug(f'{t_name} Stop window preview if any for {class_name}')
        window_name = f"{server_port}-{t_name}-{str(t_viinput)}"

        # check if window run into sub process so data come from ShareableList
        if str2bool(cfg_mgr.app_config['preview_proc']):
            cv2utils_logger.debug('Preview Window on sub process')
            sl_name = f'{t_name}_p'
            try:
                # attach to a shareable list by name
                sl = ShareableList(name=sl_name)
                sl[6] = False
                sl[18] = '0,0,0'
            except Exception as e:
                cv2utils_logger.error(f'Error to access SharedList  {sl_name} with error : {e} ')

        else:
            # for window into thread
            try:
                win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                if win != 0:
                    cv2.destroyWindow(window_name)
            except Exception as e:
                cv2utils_logger.error(f'Error on thread  {t_name} closing window with error : {e} ')


    @staticmethod
    def sl_main_proc_preview(shared_list, class_name, window_name):
        """
        Preview Window from ShareableList

        Used by platform <> win32, in this way cv2.imshow() will run on MainThread from a subprocess.
        This one will read data from a ShareAbleList created by cast thread.

        Refactored for clarity, maintainability, and robustness:
        - Uses a named tuple for shared list structure.
        - Extracts frame extraction and validation into a helper.
        - Adds explicit error logging for data mismatches.
        - Encapsulates shared list access.

        It handles potential data corruption issues during the byte-to-array
        conversion by displaying a default image if the data size is incorrect. User interactions with the preview
        window are captured, and the corresponding flags (t_preview, t_todo_stop, text) are updated in the shared list.
        The loop terminates when t_todo_stop is set or t_preview is cleared.

        Args:
            shared_list (str): Name of the shared memory list containing frame data and metadata.
            class_name (str): Name of the class or process for logging and window identification.
            window_name (str): Name of the OpenCV window to display the preview.

        Returns:
            None
        """
        # Define a named tuple for the shared list structure
        SLFields = collections.namedtuple('SLFields', [
            'total_frame', 'frame_bytes', 'server_port', 't_viinput', 't_name', 'preview_top', 't_preview',
            'preview_w', 'preview_h', 'pixel_w', 'pixel_h', 't_todo_stop', 'frame_count', 'fps', 'ip_addresses',
            'text', 'custom_text', 'cast_x', 'cast_y', 'grid', 'frame_info'
        ])

        def extract_fields(sl):
            """Extracts and returns a SLFields namedtuple from the ShareableList."""
            try:
                return SLFields(
                    sl[0], sl[1], sl[2], sl[3], sl[4], sl[5], sl[6], sl[7], sl[8], sl[9], sl[10],
                    sl[11], sl[12], sl[13], sl[14], sl[15], sl[16], sl[17], sl[18], sl[19], sl[20]
                )
            except Exception as e:
                cv2utils_logger.error(f"Error extracting fields from ShareableList: {e}")
                raise

        def get_frame_from_bytes(frame_bytes, frame_info, default_img):
            """Converts bytes to a numpy array frame, or returns default_img on error."""
            try:
                frame_data = CV2Utils.frame_remove_one(frame_bytes)
                frame_np = np.frombuffer(frame_data, dtype=np.uint8)
                shape = tuple(map(int, ast.literal_eval(frame_info)))
                expected_bytes = shape[0] * shape[1] * shape[2]
                if frame_np.nbytes == expected_bytes:
                    # shape need to be the same
                    return frame_np.reshape(shape)
                else:
                    cv2utils_logger.warning(
                        f"Frame data size mismatch: got {frame_np.nbytes}, expected {expected_bytes}. Using default image."
                    )
                    return default_img
            except Exception as e:
                cv2utils_logger.error(f"Error reconstructing frame from bytes: {e}")
                return default_img

        # attach to a shareable list by name: name is Thread Name + _p for a preview shareable list
        # sl[0]...sl[20] are used to store work data
        sl = ShareableList(name=shared_list)

        # Default image to display in case of np.array conversion problem
        default_img = cv2.imread(cfg_mgr.app_root_path('assets/Source-intro.png'))
        default_img = cv2.cvtColor(default_img, cv2.COLOR_BGR2RGB)
        default_img = CV2Utils.resize_image(default_img, 640, 360, keep_ratio=False)

        cv2utils_logger.info(f'Preview from ShareAbleList for {class_name}')

        # Check if window already exists otherwise create it
        if not CV2Utils.window_exists(window_name):
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        #
        # Display image on preview window
        # infinite loop
        #
        while True:
            fields = extract_fields(sl)

            # Generate new frame (2D) from ShareableList. Display default img in case of problem
            # original np.array has been transformed to bytes with 'tobytes()'
            # re-created as array with 'frombuffer()'
            # ... looks like some data can miss (ShareableList bug)  !!!
            # see https://github.com/python/cpython/issues/106939
            frame_to_view = get_frame_from_bytes(fields.frame_bytes, fields.frame_info, default_img)

            # Display the frame and update control flags in the shared list
            #
            # Display the frame (frame_to_view) into preview window
            # here we work with value from ShareAbleList
            #
            t_preview, t_todo_stop, text = CV2Utils.cv2_display_frame(
                fields.total_frame,
                frame_to_view,
                fields.server_port,
                fields.t_viinput,
                fields.t_name,
                fields.preview_top,
                fields.t_preview,
                fields.preview_w,
                fields.preview_h,
                fields.pixel_w,
                fields.pixel_h,
                fields.t_todo_stop,
                fields.frame_count,
                fields.fps,
                fields.ip_addresses,
                fields.text,
                fields.custom_text,
                fields.cast_x,
                fields.cast_y,
                fields.grid
            )
            # and put back new returned value into ShareAbleList
            sl[6], sl[11], sl[15] = t_preview, t_todo_stop, text

            # Stop if requested
            if t_todo_stop is True:
                cv2utils_logger.debug(f'SL STOP Cast for : {fields.t_name}')
                break
            elif t_preview is False:
                cv2utils_logger.debug(f'SL END Preview for : {fields.t_name}')
                break

        cv2utils_logger.info(f'Child process exit for : {fields.t_name}')

    @staticmethod
    def cv2_display_frame(total_frame,
                          frame,
                          server_port,
                          t_viinput,
                          t_name,
                          preview_top,
                          t_preview,
                          preview_w,
                          preview_h,
                          pixel_w,
                          pixel_h,
                          t_todo_stop,
                          frame_count,
                          fps,
                          ip_addresses,
                          text,
                          custom_text,
                          cast_x,
                          cast_y,
                          grid=False):
        """Displays a video frame in an OpenCV window with overlays and interactive controls.

        This function resizes and processes the frame, adds overlays such as text and grid, and displays it in a named
        OpenCV window.
        It also handles user keyboard input for toggling preview, text, help, and settings, and returns updated preview
        and control flags.

        Args:
            total_frame (int): Total number of frames.
            frame (np.ndarray): The image frame to display.
            server_port (int or str): Server port identifier.
            t_viinput: Video input identifier.
            t_name (str): Name of the thread or process.
            preview_top (bool): Whether to keep the window on top.
            t_preview (bool): Preview enabled flag.
            preview_w (int): Width of the preview window.
            preview_h (int): Height of the preview window.
            pixel_w (int): Pixel width for pixel art effect.
            pixel_h (int): Pixel height for pixel art effect.
            t_todo_stop (bool): Stop flag for the preview.
            frame_count (int): Current frame number.
            fps (int or float): Frames per second.
            ip_addresses (list or str): Device IP addresses.
            text (bool): Whether to show text overlays.
            custom_text (str): Custom text to display.
            cast_x (int): Grid X dimension.
            cast_y (int): Grid Y dimension.
            grid (bool, optional): Whether to overlay a grid. Defaults to False.

        Returns:
            tuple: Updated (t_preview, t_todo_stop, text) flags after user interaction.
        """
        frame = cv2.resize(frame, (preview_w, preview_h))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        if str2bool(cfg_mgr.custom_config['pixel_art']):
            frame = CV2Utils.pixelart_image(frame, pixel_w, pixel_h)

        # put text on the image
        if text:
            frame = CV2Utils.cv2_text_on_frame(frame,
                                               custom_text,
                                               preview_w,
                                               preview_h,
                                               ip_addresses,
                                               fps,
                                               server_port,
                                               frame_count,
                                               total_frame)

        window_name = f"{server_port}-{t_name}-{str(t_viinput)}"[:64]
        if grid:
            frame = ImageUtils.grid_on_image(frame, cast_x, cast_y)

        # Displaying the image
        cv2.imshow(window_name, frame)
        cv2.resizeWindow(window_name, preview_w, preview_h)

        top = 1 if preview_top is True else 0
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, top)

        key_pressed = cv2.waitKey(1)
        if key_pressed == ord("q"):  # request to stop cast
            with contextlib.suppress(Exception):
                win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                if win != 0:
                    cv2.destroyWindow(window_name)
            t_preview = False
            t_todo_stop = True
            cv2utils_logger.debug(f'Request to stop {t_name}')

        elif key_pressed == ord("p"):  # toggle preview
            with contextlib.suppress(Exception):
                win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                if win != 0:
                    cv2.destroyWindow(window_name)
            t_preview = False

        elif key_pressed == ord("t"):  # toggle text view
            text = not text

        elif key_pressed == ord("m"):  # Modify settings in a new native window
            from mainapp import CastAPI, open_webview_cast_page
            if CastAPI.loop:
                # Safely schedule the coroutine on the main event loop
                asyncio.run_coroutine_threadsafe(open_webview_cast_page(t_name), CastAPI.loop)
                cv2utils_logger.info(f"Sent request to open settings window for {t_name}")
            else:
                cv2utils_logger.error("Main event loop not available to open settings window.")

        elif key_pressed == ord("h"):  # provide help page for keys
            from mainapp import CastAPI, open_webview_help_page
            if CastAPI.loop:
                # Safely schedule the coroutine on the main event loop
                asyncio.run_coroutine_threadsafe(open_webview_help_page(), CastAPI.loop)
                cv2utils_logger.info("Sent request to open help window")
            else:
                cv2utils_logger.error("Main event loop not available to open help window.")

        return t_preview, t_todo_stop, text

    @staticmethod
    def cv2_text_on_frame(frame, custom_text, preview_w, preview_h, ip_addresses, fps, server_port, frame_count, total_frame):
        """Draws informational text overlays on a video preview frame.

        This function adds device information, frame statistics, and custom text to the top and bottom of a preview image.
        It is used to enhance the OpenCV preview window with real-time status and user-provided messages.

        Args:
            frame (np.ndarray): The image frame to annotate.
            custom_text (str): Custom text to display at the top of the frame. If empty, default info is shown.
            preview_w (int): Width of the preview window.
            preview_h (int): Height of the preview window.
            ip_addresses (list or str): List or string of device IP addresses to display.
            fps (int or float): Frames per second to display.
            server_port (int or str): Server port identifier.
            frame_count (int): Current frame number.
            total_frame (int): Total number of frames.

        Returns:
            np.ndarray: The annotated image frame.
        """
        # common param
        # font
        font = cv2.FONT_HERSHEY_SIMPLEX
        # fontScale
        fontscale = .4
        original_width = 640
        # White color in BGR
        color = (255, 255, 255)
        # Line thickness of x px
        thickness = 1

        # Calculate new font scale
        new_font_scale = fontscale * (preview_w / original_width)

        if custom_text == "":
            # bottom
            # org
            org = (50, preview_h - 50)
            x, y, w, h = 40, preview_h - 60, preview_w - 80, 15
            # Draw black background rectangle
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 0), -1)
            text_to_show_bottom = f"Device(s) : {str(ip_addresses)}"
            # Using cv2.putText() method
            frame = cv2.putText(frame,
                                text_to_show_bottom,
                                org,
                                font,
                                new_font_scale,
                                color,
                                thickness,
                                cv2.LINE_AA)

            # Top
            text_to_show = f"WLEDVideoSync: {server_port} - "
            text_to_show += f"FPS: {str(fps)} - "
            text_to_show += f"FRAME: {str(frame_count)} - "
            text_to_show += f"TOTAL: {str(total_frame)}"
        else:
            text_to_show = custom_text

        # Top
        # org
        org = (50, 50)
        x, y, w, h = 40, 15, preview_w - 80, 40
        # Draw black background rectangle
        cv2.rectangle(frame, (x, x), (x + w, y + h), (0, 0, 0), -1)
        # Using cv2.putText() method
        frame = cv2.putText(frame,
                            text_to_show,
                            org,
                            font,
                            new_font_scale,
                            color,
                            thickness,
                            cv2.LINE_AA)

        return frame

    """
    END preview window
    """

    @staticmethod
    async def get_media_info(media: str = None):
        """ retrieve cv2 info from media """
        dict_media = {}

        try:

            capture = cv2.VideoCapture(media)

            dict_media = {
                    "CV_CAP_PROP_FRAME_WIDTH": capture.get(cv2.CAP_PROP_FRAME_WIDTH),
                    "CV_CAP_PROP_FRAME_HEIGHT": capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
                    "CAP_PROP_FPS": capture.get(cv2.CAP_PROP_FPS),
                    "CAP_PROP_POS_MSEC": capture.get(cv2.CAP_PROP_POS_MSEC),
                    "CAP_PROP_FRAME_COUNT": capture.get(cv2.CAP_PROP_FRAME_COUNT),
                    "CAP_PROP_BRIGHTNESS": capture.get(cv2.CAP_PROP_BRIGHTNESS),
                    "CAP_PROP_CONTRAST": capture.get(cv2.CAP_PROP_CONTRAST),
                    "CAP_PROP_SATURATION": capture.get(cv2.CAP_PROP_SATURATION),
                    "CAP_PROP_HUE": capture.get(cv2.CAP_PROP_HUE),
                    "CAP_PROP_GAIN": capture.get(cv2.CAP_PROP_GAIN),
                    "CAP_PROP_CONVERT_RGB": capture.get(cv2.CAP_PROP_CONVERT_RGB)
            }

            # release
            capture.release()

        except Exception as e:
            cv2utils_logger.error(f'Error to get cv2 info : {e}')

        finally:
            return dict_media

    @staticmethod
    def video_to_gif(video_path, gif_path, fps, start_frame, end_frame, width=None, height=None):
        """Creates a GIF from a video file using specified start and end frames.

        Args:
            video_path (str): Path to the video file.
            gif_path (str): Path to save the GIF.
            start_frame (int): Start frame number.
            end_frame (int): End frame number.
            width (int, optional): Width to resize the GIF to. Defaults to None.
            height (int, optional): Height to resize the GIF to. Defaults to None.
            fps (int):
        """
        try:
            cap = cv2.VideoCapture(video_path)
            # fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            start_frame = max(0, min(start_frame, total_frames - 1))
            end_frame = max(start_frame + 1, min(end_frame, total_frames))

            frames = []
            for i in range(start_frame, end_frame):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if ret:
                    # select gif quality
                    if str2bool(cfg_mgr.custom_config['gif_quality']):
                        if width and height:
                            frame = cv2.resize(frame, (width, height))
                        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    else:
                        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        if width and height:
                            img = img.convert(mode='P', colors=64)
                            img = img.resize(size=(width, height), resample=1)

                    frames.append(img)

            if frames:
                duration = int(1000 / fps)  # Duration in milliseconds, based on desired FPS
                frames[0].save(gif_path,
                               save_all=True,
                               append_images=frames[1:],
                               duration=duration,
                               loop=0,
                               disposal=2)
                cv2utils_logger.info(f"GIF created successfully: {gif_path}")
            else:
                cv2utils_logger.error("No frames extracted. GIF not created.")

            cap.release()

        except Exception as e:
            cv2utils_logger.error(f"Error creating GIF: {e}")

    # resize image to specific width/height, optional ratio
    @staticmethod
    def resize_keep_aspect_ratio(image, target_width, target_height, ratio):
        """Resize an image while preserving aspect ratio.

        Crops the image to maintain the target aspect ratio before resizing.
        """

        if ratio:
            # First crop the image to the target aspect ratio
            aspect_ratio = image.shape[1] / image.shape[0]
            if target_height > 0:
                aspect_ratio = target_width / target_height
            image_aspect_ratio = image.shape[1] / image.shape[0]

            if image_aspect_ratio > aspect_ratio:
                # Crop the width
                new_width = int(image.shape[0] * aspect_ratio)
                start = (image.shape[1] - new_width) // 2
                image = image[:, start: start + new_width]
            else:
                # Crop the height
                new_height = int(image.shape[1] / aspect_ratio)
                start = (image.shape[0] - new_height) // 2
                image = image[start: start + new_height, :]

        # Resize to the target size
        image = cv2.resize(image, (target_width, target_height))
        return image

    @staticmethod
    def resize_image(image, target_width=None, target_height=None, interpolation=cv2.INTER_AREA, keep_ratio=True):
        """
        Resize the input image while maintaining the aspect ratio.

        Parameters:
        - image: Input image
        - width: Target width (optional)
        - height: Target height (optional)
        - interpolation: Interpolation method (default: cv2.INTER_AREA:3)
        - keep_ratio : preserve original ratio

        Returns:
        - Resized image
        """

        if keep_ratio:
            # Get the dimensions of the original image
            h, w = image.shape[:2]

            # Calculate aspect ratio
            aspect_ratio = w / h

            # If both width and height are None, return the original image
            if target_width is None and target_height is None:
                return image

            # If only width is provided, calculate height based on aspect ratio
            if target_width is not None and target_height is None:
                target_height = int(target_width / aspect_ratio)

            elif target_width is None:
                target_width = int(target_height * aspect_ratio)

        interpolation = int(cfg_mgr.app_config['interpolation'])

        return cv2.resize(
            image, (target_width, target_height), interpolation=interpolation
        )

    @staticmethod
    def pixelart_image(image_np, width_x, height_y):
        """ Convert image array to pixel art using cv """

        # Get input size
        orig_height, orig_width = image_np.shape[:2]
        # Desired "pixelated" size
        w, h = (width_x, height_y)

        # Resize input to "pixelated" size
        temp_img = cv2.resize(image_np, (w, h), interpolation=cv2.INTER_LINEAR)
        
        return cv2.resize(
            temp_img, (orig_width, orig_height), interpolation=cv2.INTER_NEAREST
        )

    @staticmethod
    def save_image(class_obj, buffer, image_number, ascii_art=False):
        """
        Save image from Buffer
        used on the buffer images
        """
        # Get the absolute path of the folder
        absolute_img_folder = cfg_mgr.app_root_path(cfg_mgr.app_config['img_folder'])
        if not os.path.isdir(absolute_img_folder):
            cv2utils_logger.error(f"The folder {absolute_img_folder} does not exist.")
            return

        # select buffer
        if buffer == 'frame_buffer':
            buffer = class_obj.frame_buffer
        else:
            buffer = class_obj.cast_frame_buffer

        w, h = buffer[image_number].shape[:2]
        date_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        class_name = class_obj.__module__

        if ascii_art:
            img = buffer[image_number]
            img = Image.fromarray(img)
            img = ImageUtils.image_to_ascii(img)
            t_filename = os.path.join(
                absolute_img_folder,
                (
                    (
                        (
                            (
                                f"{class_name}_{str(image_number)}_{str(w)}_"
                                + str(h)
                            )
                            + "_"
                        )
                        + date_time
                    )
                    + ".txt"
                ),
            )
            with open(t_filename, 'w') as ascii_file:
                ascii_file.write(img)

        else:
            t_filename = os.path.join(
                absolute_img_folder,
                (
                    (
                        (
                            (
                                f"{class_name}_{str(image_number)}_{str(w)}_"
                                + str(h)
                            )
                            + "_"
                        )
                        + date_time
                    )
                    + ".jpg"
                ),
            )
            img = cv2.cvtColor(buffer[image_number], cv2.COLOR_RGB2BGR)
            cv2.imwrite(t_filename, img)

        cv2utils_logger.debug(f"Image saved to {t_filename}")


class ImageUtils:
    """Provides utility functions for image processing and manipulation.

    This class offers static methods for applying filters, converting images
    to ASCII art, drawing grids on images, and adjusting brightness and
    contrast.
    """
    @staticmethod
    def image_array_to_base64(nparray):
        """Convert an image array to a Base64 string.

        Converts a NumPy array representing an image to a Base64 encoded string, suitable for embedding in HTML or 
        other text-based formats.
        """
        # Convert NumPy array to PIL Image
        image = Image.fromarray(nparray)
        # Save the image to a bytes buffer
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    @staticmethod
    def process_filters_image(img: np.ndarray, filters: dict) -> np.ndarray:
        """Process image filters.

        Applies a set of filters to an image using OpenCV.  The filters are specified as a dictionary, 
        where keys are filter names and values are filter parameters.
        """
        img = ImageUtils.apply_filters_cv2(img, filters)
        return img

    @staticmethod
    def apply_filters_cv2(img: np.ndarray, filters: dict) -> np.ndarray:
        """Apply filters to an image using OpenCV.

        Applies various image filters like saturation, brightness, contrast, sharpen, and color balance to 
        the input image.  The filters and their parameters are specified in the `filters` dictionary.
        """
        # Convert to HSV for color adjustment
        if filters["saturation"] != 0:
            img = ImageUtils.filter_saturation(img, filters["saturation"])

        # Adjust brightness
        if filters["brightness"] != 0:
            img = ImageUtils.filter_brightness(img, filters["brightness"])

        # Adjust contrast
        if filters["contrast"] != 0:
            img = ImageUtils.filter_contrast(img, filters["contrast"])

        if filters["sharpen"] != 0:
            img = ImageUtils.filter_sharpen(img, filters["sharpen"])

        if filters["balance_r"] != 0 or filters["balance_g"] != 0 or filters['balance_b'] != 0:
            img = ImageUtils.filter_balance(
                img,
                {
                    "r": filters["balance_r"],
                    "g": filters["balance_g"],
                    "b": filters["balance_b"],
                },
            )

        return img

    @staticmethod
    def filter_balance(img, alpha):
        """Adjust color balance of an image.

        Scales the red, green, and blue channels of the image by the factors specified in the `alpha` dictionary.
        """
        # scale the red, green, and blue channels
        scale = np.array([alpha["r"], alpha["g"], alpha["b"]])[np.newaxis, np.newaxis, :]

        img = (img * scale).astype(np.uint8)
        return img

    @staticmethod
    def filter_saturation(img, alpha):
        """Adjust the saturation of an image.

        Enhances or reduces the saturation of an image by blending the original image with a grayscale version.
        """
        # Convert to HSV and split the channels
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)

        # Create a grayscale (desaturated) version
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        # Enhance color
        s_enhanced = cv2.addWeighted(s, alpha, gray, 1 - alpha, 0)

        return cv2.cvtColor(cv2.merge([h, s_enhanced, v]), cv2.COLOR_HSV2RGB)

    @staticmethod
    def filter_brightness(img, alpha):
        """Adjust the brightness of an image.

        Changes the brightness of an image by blending it with a black image.  The `alpha` parameter controls the 
        blending ratio.
        """
        # Create a black image
        black_img = np.zeros_like(img)

        return cv2.addWeighted(img, alpha, black_img, 1 - alpha, 0)

    @staticmethod
    def filter_contrast(img, alpha):
        """Adjust the contrast of an image.

        Modifies the contrast of an image by blending it with a gray image of mean luminance.  
        The `alpha` parameter controls the blending ratio.
        """
        # Compute the mean luminance (gray level)
        mean_luminance = np.mean(img)

        # Create a gray image of mean luminance
        gray_img = np.full_like(img, mean_luminance)

        return cv2.addWeighted(img, alpha, gray_img, 1 - alpha, 0)

    @staticmethod
    def filter_sharpen(img, alpha):
        """Sharpen an image using a Laplacian kernel.

        Applies a sharpening filter to the image using a Laplacian kernel scaled by the `alpha` parameter.
        """
        kernel = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]]) * alpha
        kernel[1, 1] += 1
        img = cv2.filter2D(img, -1, kernel)
        return img

    @staticmethod
    def image_to_ascii(image):
        """Convert an image to ASCII art.

        Transforms a PIL Image into an ASCII art representation using a set of characters to approximate 
        grayscale values.  The resulting ASCII art is returned as a string.
        """
        # Convert the image to ASCII art
        ascii_chars = "@%#*+=-:. "
        width, height = image.size
        image = image.resize((width, height // 2))  # Correct aspect ratio
        image = image.convert("L")  # Convert to grayscale
        pixels = image.getdata()
        ascii_str = ""
        for pixel_value in pixels:
            ascii_str += ascii_chars[
                pixel_value // 32
                ]  # Map the pixel value to ascii_chars
        ascii_str_len = len(ascii_str)
        ascii_img = ""
        for i in range(0, ascii_str_len, width):
            ascii_img += ascii_str[i: i + width] + "\n"
        return ascii_img

    @staticmethod
    def grid_on_image(image, cols, rows):
        """Draw a grid and cell numbers on an image.

        Overlays a grid with the specified number of columns and rows onto the image.  
        Each cell in the grid is numbered for identification.
        """

        if cols == 0 or rows == 0:
            cv2utils_logger.error('Rows / cols should not be zero')

        else:

            # Calculate cell size based on image dimensions and grid size
            cell_width = image.shape[1] // cols
            cell_height = image.shape[0] // rows

            # Calculate font size based on image size
            font_scale = min(image.shape[0], image.shape[1]) // 250
            font_scale = max(font_scale, .3)
            # Draw the grid
            for i in range(1, rows):
                cv2.line(image, (0, i * cell_height), (image.shape[1], i * cell_height), (255, 255, 255), 2)
            for j in range(1, cols):
                cv2.line(image, (j * cell_width, 0), (j * cell_width, image.shape[0]), (255, 255, 255), 2)

            # Add numbers to the grid
            count = 0
            for i in range(rows):
                for j in range(cols):
                    # Calculate text position dynamically
                    text_x = j * cell_width + int(0.1 * cell_width)
                    text_y = i * cell_height + int(0.8 * cell_height)
                    cv2.putText(image, str(count), (text_x, text_y),
                                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 2)
                    count += 1

        return image

    @staticmethod
    def automatic_brightness_and_contrast(image, clip_hist_percent=25):
        """Automatically adjust brightness and contrast of an image.

        Calculates the optimal brightness and contrast values based on the image's histogram and applies them 
        to enhance the image's dynamic range.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Calculate grayscale histogram
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist_size = len(hist)

        # Calculate cumulative distribution from the histogram
        accumulator = [float(hist[0])]

        accumulator.extend(
            accumulator[index - 1] + float(hist[index])
            for index in range(1, hist_size)
        )
        # Locate points to clip
        maximum = accumulator[-1]
        clip_hist_percent *= (maximum / 100.0)
        clip_hist_percent /= 2.0

        # Locate left cut
        minimum_gray = 0
        while accumulator[minimum_gray] < clip_hist_percent:
            minimum_gray += 1

        # Locate right cut
        maximum_gray = hist_size - 1
        with contextlib.suppress(IndexError):
            while accumulator[maximum_gray] >= (maximum - clip_hist_percent):
                maximum_gray -= 1
        # Calculate alpha and beta values
        if maximum_gray - minimum_gray > 0:
            alpha = 255 / (maximum_gray - minimum_gray)
        else:
            alpha = 255 / .1
        beta = -minimum_gray * alpha

        return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)

    @staticmethod
    def gamma_correct_frame(gamma: float = 0.5):
        """Generate a gamma correction lookup table.

        Creates a lookup table for gamma correction, which can be used to adjust the gamma of an image using cv2.LUT.
        """
        inverse_gamma = 1 / gamma
        gamma_table = [((i / 255) ** inverse_gamma) * 255 for i in range(256)]
        return np.array(gamma_table, np.uint8)


class VideoThumbnailExtractor:
    """
    Extract thumbnails from a video or image file.

    thumbnail_width: 160 by default
    get_thumbnails: return a list of numpy arrays (RGB)

    # Usage
    video_path = "path/to/your/video.mp4"
    extractor = VideoThumbnailExtractor(video_path)
    extractor.extract_thumbnails(times_in_seconds=[10, 20, 30])  # Extract thumbnails at specified times

    thumbnail_frames = extractor.get_thumbnails()

    for i, thumbnail_frame in enumerate(thumbnail_frames):
        if thumbnail_frame is not None:
            # Display the thumbnail using OpenCV
            cv2.imshow(f'Thumbnail {i+1}', thumbnail_frame)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print(f"No thumbnail extracted at time {i}.")
    """

    def __init__(self, media_path, thumbnail_width=160):
        self.media_path = media_path
        self.thumbnail_width = thumbnail_width
        self.thumbnail_frames = []

    async def is_image_file(self):
        """Check if the media path is an image file.

        Checks if the file extension of the media path matches common image formats.
        """
        # Check if the file extension is an image format
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        _, ext = os.path.splitext(self.media_path)
        return ext.lower() in image_extensions

    async def is_video_file(self):
        """Check if the media path is a video file.

        Attempts to open the media path using cv2.VideoCapture and reads a frame to verify if it's a valid video.
         Releases the capture object regardless of success.
        """
        # Check if the file can be opened as a video
        cap = cv2.VideoCapture(self.media_path)
        if not cap.isOpened():
            return False
        ret, _ = cap.read()
        cap.release()
        return ret

    async def extract_thumbnails(self, times_in_seconds=None):
        """Extract thumbnails from media.

        Extracts thumbnails from a video or image file at specified times or from the entire image.
        Generates blank frames if the media file is invalid.
        """
        if times_in_seconds is None:
            times_in_seconds = [5]
        if await self.is_image_file():
            await self.extract_thumbnails_from_image()
        elif await self.is_video_file():
            await self.extract_thumbnails_from_video(times_in_seconds)
        else:
            # Provide blank frames if the file is not a valid media file
            self.thumbnail_frames = [await self.create_blank_frame() for _ in times_in_seconds]
            cv2utils_logger.warning(f"{self.media_path} is not a valid media file. Generated blank frames.")

    async def extract_thumbnails_from_image(self):
        """Extract a thumbnail from an image.

        Reads an image file, resizes it to the specified thumbnail width while maintaining aspect ratio,
        and stores it as a thumbnail frame.  Generates a blank frame if image reading fails.
        """
        image = cv2.imread(self.media_path)
        if image is not None:
            await self.resize_thumbnails_from_image(image)
        else:
            self.thumbnail_frames = [await self.create_blank_frame()]
            cv2utils_logger.error("Failed to read image. Generated a blank frame.")

    async def resize_thumbnails_from_image(self, image):
        # Resize the image to the specified thumbnail width while maintaining aspect ratio
        height, width, _ = image.shape
        aspect_ratio = height / width
        new_height = int(self.thumbnail_width * aspect_ratio)
        resized_image = cv2.resize(image, (self.thumbnail_width, new_height))
        self.thumbnail_frames = [resized_image]  # Single thumbnail for images
        cv2utils_logger.debug(f"Thumbnail extracted from image: {self.media_path}")

    async def extract_thumbnails_from_video(self, times_in_seconds):
        """Extract thumbnails from a video at specified times.

        Reads frames from a video file at specified time offsets and resizes them to create thumbnails.
        Handles cases where the specified time exceeds the video length and generates blank frames if extraction fails.
        """
        cap = cv2.VideoCapture(self.media_path)
        if not cap.isOpened():
            cv2utils_logger.error(f"Failed to open video file: {self.media_path}")
            self.thumbnail_frames = [await self.create_blank_frame() for _ in times_in_seconds]
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        video_length = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps

        for time_in_seconds in times_in_seconds:
            if time_in_seconds > video_length:
                cv2utils_logger.warning(f"Specified time {time_in_seconds}s is greater than video length {video_length}s. "
                               f"Setting time to {video_length}s.")
                time_in_seconds = video_length

            frame_number = int(time_in_seconds * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            success, frame = cap.read()

            if success:
                # Resize the frame to the specified thumbnail width while maintaining aspect ratio
                height, width, _ = frame.shape
                aspect_ratio = height / width
                new_height = int(self.thumbnail_width * aspect_ratio)
                resized_frame = cv2.resize(frame, (self.thumbnail_width, new_height))

                self.thumbnail_frames.append(resized_frame)
                cv2utils_logger.debug(f"Thumbnail extracted at {time_in_seconds}s.")
            else:
                cv2utils_logger.error("Failed to extract frame.")
                self.thumbnail_frames.append(await self.create_blank_frame())

        cap.release()

    async def create_blank_frame(self):
        """Create a blank frame for thumbnail.

        Generates a blank placeholder frame with dimensions based on the thumbnail width and a 16:9 aspect ratio.
        The frame is filled with random noise.
        """
        # Create a blank frame with the specified thumbnail width and a default height
        height = int(self.thumbnail_width * 9 / 16)  # Assuming a 16:9 aspect ratio for the blank frame
        return np.random.randint(
            0, 256, (height, self.thumbnail_width, 3), dtype=np.uint8
        )

    async def get_thumbnails(self):
        """Get the extracted thumbnails.

        Returns a list of thumbnail frames as RGB NumPy arrays.  Converts BGR images to RGB before returning.
        """
        return [cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) for frame in self.thumbnail_frames]
