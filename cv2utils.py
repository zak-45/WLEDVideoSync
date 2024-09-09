"""
# a: zak-45
# d: 23/08/2024
# v: 1.0.0
#
# CV2Utils
#
#          CAST utilities
#
# Image utilities
# cv2 preview
#
"""

import cv2
from multiprocessing.shared_memory import ShareableList
import numpy as np
import logging
import logging.config
import concurrent_log_handler
from PIL import Image
import io
import base64
import os
import cfg_load as cfg
from str2bool import str2bool


class CV2Utils:

    def __init__(self):
        pass

    @staticmethod
    def cv2_win_close(server_port, class_name, t_name, t_viinput):
        """ Close cv2 window created by imshow """

        logger.info(f'{t_name} Stop window preview if any')
        window_name = f"{server_port}-{class_name} Preview input: " + str(t_viinput) + str(t_name)

        # check if window run into sub process to instruct it by ShareableList
        config_data = CV2Utils.read_config()
        preview_proc = str2bool(config_data[1]['preview_proc'])

        # for window into sub process
        if preview_proc:
            logger.debug('Window on sub process')
            try:
                # attach to a shareable list by name
                sl = ShareableList(name=t_name)
                sl[6] = False
                sl[18] = '0,0,0'
            except Exception as t_error:
                logger.error(f'Error to access SharedList  {t_name} with error : {t_error} ')

        else:

            # for window into thread
            try:
                win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                if not win == 0:
                    cv2.destroyWindow(window_name)
            except Exception as t_error:
                logger.error(f'Error on thread  {t_name} closing window with error : {t_error} ')

    @staticmethod
    def sl_main_preview(shared_list, class_name):
        """
        Used by platform <> win32, in this way cv2.imshow() will run on MainThread from a subprocess
        This one will read data from a ShareAbleList created by cast thread
        Updated data are: t_preview, to_todo_stop and text caught from user entry on preview window
        :param class_name:  Desktop or Media
        :param shared_list:
        :return:
        """
        # Default image to display in case of np.array conversion problem
        sl_img = cv2.imread('assets/Source-intro.png')
        sl_img = cv2.cvtColor(sl_img, cv2.COLOR_BGR2RGB)
        sl_img = CV2Utils.resize_image(sl_img, 640, 360, keep_ratio=False)

        # attach to a shareable list by name: name is Thread Name
        sl = ShareableList(name=shared_list)

        # Display image on preview window
        while True:
            # Data from shared List
            sl_total_frame = sl[0]
            # remove the last byte and convert back to numpy
            sl_frame = bytearray(sl[1])
            sl_frame = sl_frame[:-1]
            sl_frame = bytes(sl_frame)
            sl_frame = np.frombuffer(sl_frame, dtype=np.uint8)
            #
            sl_server_port = sl[2]
            sl_t_viinput = sl[3]
            sl_t_name = sl[4]
            sl_preview_top = sl[5]
            sl_t_preview = sl[6]
            sl_preview_w = sl[7]
            sl_preview_h = sl[8]
            sl_t_todo_stop = sl[9]
            sl_frame_count = sl[10]
            sl_fps = sl[11]
            sl_ip_addresses = sl[12]
            sl_text = sl[13]
            sl_custom_text = sl[14]
            sl_cast_x = sl[15]
            sl_cast_y = sl[16]
            sl_grid = sl[17]
            received_shape = sl[18].split(',')

            # calculate new shape value, if 0 then stop preview
            # ( w * h * (colors number)) e.g. 640(w) * 360()h * 3(rgb)
            shape_bytes = int(received_shape[0]) * int(received_shape[1]) * int(received_shape[2])
            if shape_bytes == 0:
                window_name = f"{sl_server_port}-{class_name} Preview input: " + str(sl_t_viinput) + str(sl_t_name)
                try:
                    win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                    if not win == 0:
                        cv2.destroyWindow(window_name)
                except:
                    pass
                break
            # Generate new frame from ShareableList. Display default img in case of problem
            # original np.array has been transformed to bytes with 'tobytes()'
            # re-created as array with 'frombuffer()'
            # ... looks like some data can miss (ShareableList bug)  !!!
            # see https://github.com/python/cpython/issues/106939
            # shape need to be the same
            if sl_frame.nbytes == shape_bytes:
                # we need to reshape the array to provide right dim. ( w, h, 3-->rgb)
                received_frame = sl_frame.reshape(int(received_shape[0]), int(received_shape[1]), -1)
            else:
                # in case of any array data/size problem
                logger.debug(received_shape, shape_bytes, sl_frame.nbytes)
                received_frame = sl_img

            sl[6], sl[9], sl[13] = CV2Utils.cv2_preview_window(
                sl_total_frame,
                received_frame,
                sl_server_port,
                sl_t_viinput,
                sl_t_name,
                sl_preview_top,
                sl_t_preview,
                sl_preview_w,
                sl_preview_h,
                sl_t_todo_stop,
                sl_frame_count,
                sl_fps,
                sl_ip_addresses,
                sl_text,
                sl_custom_text,
                sl_cast_x,
                sl_cast_y,
                class_name,
                sl_grid)

            # Stop if requested
            if sl[9] is True:
                sl[18] = '0,0,0'
                logger.info(f'STOP Cast for : {sl_t_name}')
                break
            elif sl[6] is False:
                logger.info(f'END Preview for : {sl_t_name}')
                break

        logger.info(f'Child process exit for : {sl_t_name}')

    @staticmethod
    def cv2_preview_window(total_frame,
                           frame,
                           server_port,
                           t_viinput,
                           t_name,
                           preview_top,
                           t_preview,
                           preview_w,
                           preview_h,
                           t_todo_stop,
                           frame_count,
                           fps,
                           ip_addresses,
                           text,
                           custom_text,
                           cast_x,
                           cast_y,
                           class_name,
                           grid=False):
        """
        CV2 preview window
        Main logic for imshow() and waitKey()
        """

        frame = cv2.resize(frame, (preview_w, preview_h))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # put text on the image
        if text:
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
                text_to_show_bottom = "Device(s) : "
                text_to_show_bottom += str(ip_addresses)
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
                text_to_show += "FPS: " + str(fps) + " - "
                text_to_show += "FRAME: " + str(frame_count) + " - "
                text_to_show += "TOTAL: " + str(total_frame)
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

        # Displaying the image
        window_name = f"{server_port}-{class_name} Preview input: " + str(t_viinput) + str(t_name)
        if grid:
            frame = ImageUtils.grid_on_image(frame, cast_x, cast_y)

        cv2.imshow(window_name, frame)
        cv2.resizeWindow(window_name, preview_w, preview_h)

        top = 0
        if preview_top is True:
            top = 1
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, top)
        key_pressed = cv2.waitKey(1)
        if key_pressed == ord("q"):
            try:
                win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                if not win == 0:
                    cv2.destroyWindow(window_name)
            except:
                pass
            t_preview = False
            t_todo_stop = True
            logger.info(f'Request to stop {t_name}')
        elif key_pressed == ord("p"):
            try:
                win = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                if not win == 0:
                    cv2.destroyWindow(window_name)
            except:
                pass
            t_preview = False
        elif key_pressed == ord("t"):
            if text:
                text = False
            else:
                text = True

        return t_preview, t_todo_stop, text

    """
    END preview window
    """

    @staticmethod
    def get_media_info(media: str = None):
        """ retrieve cv2 info from media """
        dict_media = []

        try:

            capture = cv2.VideoCapture(media)

            # showing values of the properties
            dict_media.append('"CV_CAP_PROP_FRAME_WIDTH": "{}"'.format(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
            dict_media.append('"CV_CAP_PROP_FRAME_HEIGHT" : "{}"'.format(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            dict_media.append('"CAP_PROP_FPS" : "{}"'.format(capture.get(cv2.CAP_PROP_FPS)))
            dict_media.append('"CAP_PROP_POS_MSEC" : "{}"'.format(capture.get(cv2.CAP_PROP_POS_MSEC)))
            dict_media.append('"CAP_PROP_FRAME_COUNT" : "{}"'.format(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
            dict_media.append('"CAP_PROP_BRIGHTNESS" : "{}"'.format(capture.get(cv2.CAP_PROP_BRIGHTNESS)))
            dict_media.append('"CAP_PROP_CONTRAST" : "{}"'.format(capture.get(cv2.CAP_PROP_CONTRAST)))
            dict_media.append('"CAP_PROP_SATURATION" : "{}"'.format(capture.get(cv2.CAP_PROP_SATURATION)))
            dict_media.append('"CAP_PROP_HUE" : "{}"'.format(capture.get(cv2.CAP_PROP_HUE)))
            dict_media.append('"CAP_PROP_GAIN" : "{}"'.format(capture.get(cv2.CAP_PROP_GAIN)))
            dict_media.append('"CAP_PROP_CONVERT_RGB" : "{}"'.format(capture.get(cv2.CAP_PROP_CONVERT_RGB)))

            # release
            capture.release()

        except Exception as e:
            logger.error(f'Error to get cv2 info : {e}')

        return dict_media

    # resize image to specific width/height, optional ratio
    @staticmethod
    def resize_keep_aspect_ratio(image, target_width, target_height, ratio):

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
        - interpolation: Interpolation method (default: cv2.INTER_AREA)
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

            # If only height is provided, calculate width based on aspect ratio
            elif target_height is not None and target_width is None:
                target_width = int(target_height * aspect_ratio)

            # Resize image
            resized_image = cv2.resize(image, (target_width, target_height), interpolation=interpolation)

        else:
            # Resize image
            resized_image = cv2.resize(image, (target_width, target_height), interpolation=interpolation)

        return resized_image

    @staticmethod
    def pixelart_image(image_np, width_x, height_y):
        """ Convert image array to pixel art using cv """

        # Get input size
        orig_height, orig_width = image_np.shape[:2]
        # Desired "pixelated" size
        w, h = (width_x, height_y)

        # Resize input to "pixelated" size
        temp_img = cv2.resize(image_np, (w, h), interpolation=cv2.INTER_LINEAR)
        # Initialize output image
        pixelart_img = cv2.resize(temp_img, (orig_width, orig_height), interpolation=cv2.INTER_NEAREST)

        return pixelart_img

    @staticmethod
    def setup_logging(config_path='logging_config.ini', handler_name: str = None):
        if os.path.exists(config_path):
            logging.config.fileConfig(config_path, disable_existing_loggers=False)
            # trick: use the same name for all modules, ui.log will receive message from alls
            config_data = CV2Utils.read_config()
            if str2bool(config_data[1]['log_to_main']):
                v_logger = logging.getLogger('WLEDLogger')
            else:
                v_logger = logging.getLogger(handler_name)
            v_logger.info(f"Logging configured using {config_path} for {handler_name}")
        else:
            logging.basicConfig(level=logging.INFO)
            v_logger = logging.getLogger(handler_name)
            v_logger.warning(f"Logging config file {config_path} not found. Using basic configuration.")

        return v_logger

    @staticmethod
    def read_config():
        # load config file
        cast_config = cfg.load('config/WLEDVideoSync.ini')
        # config keys
        server_config = cast_config.get('server')
        app_config = cast_config.get('app')
        colors_config = cast_config.get('colors')
        custom_config = cast_config.get('custom')
        preset_config = cast_config.get('presets')

        return server_config, app_config, colors_config, custom_config, preset_config


class ImageUtils:

    @staticmethod
    def image_array_to_base64(nparray):
        # Convert NumPy array to PIL Image
        image = Image.fromarray(nparray)
        # Save the image to a bytes buffer
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        # Encode the bytes as Base64
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        # The img_str is the Base64 string representation of the image
        return img_str

    @staticmethod
    def process_raw_image(img: np.ndarray, filters: dict) -> np.ndarray:
        img = ImageUtils.apply_filters_cv2(img, filters)
        return img

    @staticmethod
    def apply_filters_cv2(img: np.ndarray, filters: dict) -> np.ndarray:
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
        # scale the red, green, and blue channels
        scale = np.array([alpha["r"], alpha["g"], alpha["b"]])[np.newaxis, np.newaxis, :]

        img = (img * scale).astype(np.uint8)
        return img

    @staticmethod
    def filter_saturation(img, alpha):
        # Convert to HSV and split the channels
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)

        # Create a grayscale (desaturated) version
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        # Enhance color
        s_enhanced = cv2.addWeighted(s, alpha, gray, 1 - alpha, 0)

        # Merge and convert back to RGB
        enhanced_img = cv2.cvtColor(cv2.merge([h, s_enhanced, v]), cv2.COLOR_HSV2RGB)
        return enhanced_img

    @staticmethod
    def filter_brightness(img, alpha):
        # Create a black image
        black_img = np.zeros_like(img)

        # Enhance brightness
        enhanced_img = cv2.addWeighted(img, alpha, black_img, 1 - alpha, 0)
        return enhanced_img

    @staticmethod
    def filter_contrast(img, alpha):
        # Compute the mean luminance (gray level)
        mean_luminance = np.mean(img)

        # Create a gray image of mean luminance
        gray_img = np.full_like(img, mean_luminance)

        # Enhance contrast
        enhanced_img = cv2.addWeighted(img, alpha, gray_img, 1 - alpha, 0)
        return enhanced_img

    @staticmethod
    def filter_sharpen(img, alpha):
        kernel = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]]) * alpha
        kernel[1, 1] += 1
        img = cv2.filter2D(img, -1, kernel)
        return img

    @staticmethod
    def image_to_ascii(image):
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

        if cols == 0 or rows == 0:
            logger.error('Rows / cols should not be zero')

        else:

            # Calculate cell size based on image dimensions and grid size
            cell_width = image.shape[1] // cols
            cell_height = image.shape[0] // rows

            # Calculate font size based on image size
            font_scale = min(image.shape[0], image.shape[1]) // 250
            if font_scale < .3:
                font_scale = .3

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
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Calculate grayscale histogram
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist_size = len(hist)

        # Calculate cumulative distribution from the histogram
        accumulator = [float(hist[0])]

        for index in range(1, hist_size):
            accumulator.append(accumulator[index - 1] + float(hist[index]))

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
        try:
            while accumulator[maximum_gray] >= (maximum - clip_hist_percent):
                maximum_gray -= 1
        except IndexError as error:
            pass

        # Calculate alpha and beta values
        if maximum_gray - minimum_gray > 0:
            alpha = 255 / (maximum_gray - minimum_gray)
        else:
            alpha = 255 / .1
        beta = -minimum_gray * alpha

        auto_image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)

        return auto_image

    @staticmethod
    def gamma_correct_frame(gamma: float = 0.5):

        inverse_gamma = 1 / gamma
        gamma_table = [((i / 255) ** inverse_gamma) * 255 for i in range(256)]
        gamma_table = np.array(gamma_table, np.uint8)

        return gamma_table


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

    def is_image_file(self):
        # Check if the file extension is an image format
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        _, ext = os.path.splitext(self.media_path)
        return ext.lower() in image_extensions

    def is_video_file(self):
        # Check if the file can be opened as a video
        cap = cv2.VideoCapture(self.media_path)
        if not cap.isOpened():
            return False
        ret, _ = cap.read()
        cap.release()
        return ret

    async def extract_thumbnails(self, times_in_seconds=None):
        if times_in_seconds is None:
            times_in_seconds = [5]
        if self.is_image_file():
            self.extract_thumbnails_from_image()
        elif self.is_video_file():
            await self.extract_thumbnails_from_video(times_in_seconds)
        else:
            # Provide blank frames if the file is not a valid media file
            self.thumbnail_frames = [self.create_blank_frame() for _ in times_in_seconds]
            logger.warning(f"{self.media_path} is not a valid media file. Generated blank frames.")

    def extract_thumbnails_from_image(self):
        image = cv2.imread(self.media_path)
        if image is not None:
            # Resize the image to the specified thumbnail width while maintaining aspect ratio
            height, width, _ = image.shape
            aspect_ratio = height / width
            new_height = int(self.thumbnail_width * aspect_ratio)
            resized_image = cv2.resize(image, (self.thumbnail_width, new_height))
            self.thumbnail_frames = [resized_image]  # Single thumbnail for images
            logger.debug(f"Thumbnail extracted from image: {self.media_path}")
        else:
            self.thumbnail_frames = [self.create_blank_frame()]
            logger.error("Failed to read image. Generated a blank frame.")

    async def extract_thumbnails_from_video(self, times_in_seconds):
        cap = cv2.VideoCapture(self.media_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video file: {self.media_path}")
            self.thumbnail_frames = [self.create_blank_frame() for _ in times_in_seconds]
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        video_length = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps

        for time_in_seconds in times_in_seconds:
            if time_in_seconds > video_length:
                logger.warning(f"Specified time {time_in_seconds}s is greater than video length {video_length}s. "
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
                logger.info(f"Thumbnail extracted at {time_in_seconds}s.")
            else:
                logger.error("Failed to extract frame.")
                self.thumbnail_frames.append(self.create_blank_frame())

        cap.release()

    def create_blank_frame(self):
        # Create a blank frame with the specified thumbnail width and a default height
        height = int(self.thumbnail_width * 9 / 16)  # Assuming a 16:9 aspect ratio for the blank frame
        blank_frame = np.random.randint(0, 256, (height, self.thumbnail_width, 3), dtype=np.uint8)
        # blank_frame = np.zeros((height, self.thumbnail_width, 3), np.uint8)
        # blank_frame[:] = (255, 255, 255)  # White blank frame
        return blank_frame

    def get_thumbnails(self):
        return [cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) for frame in self.thumbnail_frames]


"""
When this env var exist, this mean run from the one-file compressed executable.
Load of the config is not possible, folder config should not exist.
This avoid FileNotFoundError.
This env not exist when run from the extracted program.
Expected way to work.
"""
if "NUITKA_ONEFILE_PARENT" not in os.environ:
    # read config
    # create logger
    logger = CV2Utils.setup_logging('config/logging.ini', 'WLEDLogger.utils')
