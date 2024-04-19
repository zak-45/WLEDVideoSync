import cv2
import numpy as np
import pymonctl


def process_raw_image(img: np.ndarray, resolution: Size, filters: dict) -> np.ndarray:
    img = cv2.resize(img, resolution, interpolation=cv2.INTER_AREA)
    img = apply_filters_cv2(img, filters)
    return img


def apply_filters_cv2(img: np.ndarray, filters: dict) -> np.ndarray:
    # Convert to HSV for color adjustment
    if filters["saturation"] is not None:
        img = filter_saturation(img, filters["saturation"])

    # Adjust brightness
    if filters["brightness"] is not None:
        img = filter_brightness(img, filters["brightness"])

    # Adjust contrast
    if filters["contrast"] is not None:
        img = filter_contrast(img, filters["contrast"])

    if filters["sharpen"] is not None:
        img = filter_sharpen(img, filters["sharpen"])

    if filters["balance_r"] is not None:
        img = filter_balance(
            img,
            {
                "r": filters["balance_r"],
                "g": filters["balance_g"],
                "b": filters["balance_b"],
            },
        )

    return img


def filter_sharpen(img, alpha):
    kernel = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]]) * alpha
    kernel[1, 1] += 1
    img = cv2.filter2D(img, -1, kernel)
    return img


def filter_balance(img, alpha):
    # scale the red, green, and blue channels
    scale = np.array([alpha["r"], alpha["g"], alpha["b"]])[np.newaxis, np.newaxis, :]

    img = (img * scale).astype(np.uint8)
    return img


def filter_contrast(img, alpha):
    # Compute the mean luminance (gray level)
    mean_luminance = np.mean(img)

    # Create a gray image of mean luminance
    gray_img = np.full_like(img, mean_luminance)

    # Enhance contrast
    enhanced_img = cv2.addWeighted(img, alpha, gray_img, 1 - alpha, 0)
    return enhanced_img


def filter_brightness(img, alpha):
    # Create a black image
    black_img = np.zeros_like(img)

    # Enhance brightness
    enhanced_img = cv2.addWeighted(img, alpha, black_img, 1 - alpha, 0)
    return enhanced_img


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


def show_preview(rgb_array, resolution):
    # Show a live view of the downscaled feed on the computer with 24-bit color blocks
    # Scaling by an integer will keep the pixelated effect but make it visible
    x, y = resolution
    monitor_x, monitor_y = pymonctl.getPrimary().size
    # find the largest integer scaling factor that will fit in the monitor in both dimensions
    scaling_factor = min(monitor_x // x, monitor_y // y)
    bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    if scaling_factor > 1:
        bgr_array = stretch_array_repeat(bgr_array, scaling_factor)
    try:
        # Use OpenCV to display the image
        cv2.imshow("Live View", bgr_array)
        cv2.waitKey(1)

    except Exception as error:
        print(f"An error occurred during live view: {error}")


def stretch_array_repeat(arr, stretch_factor):
    # Repeat the array elements along the column axis
    stretched_arr = np.repeat(arr, stretch_factor, axis=0)
    # Repeat the array elements along the row axis
    stretched_arr = np.repeat(stretched_arr, stretch_factor, axis=1)
    return stretched_arr
