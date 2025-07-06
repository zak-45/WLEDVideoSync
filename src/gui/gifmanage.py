from unidecode import unidecode # For robust filename transliteration
from nicegui import ui, run
import os
from pathlib import Path
import aiohttp  # For asynchronous HTTP requests to WLED (file upload)
from wled import WLED  # For WLED JSON API interactions
from wled.exceptions import WLEDConnectionError, WLEDError # Specific WLED errors


import asyncio
import re # For filename cleaning

# Assuming these are available from your project structure
from configmanager import cfg_mgr, LoggerManager

# from src.utl.utils import Utils # If you have WLED helpers there


# Setup logger for this page
logger_manager = LoggerManager(logger_name='WLEDLogger.utils')
page_logger = logger_manager.logger

# --- Configuration ---
# Directory where your GIFs are stored, relative to the app's media path
GIF_SUBDIR = 'gif'
# Full path to the GIF directory
GIF_DIR_PATH = Path(cfg_mgr.app_root_path('media')) / GIF_SUBDIR
# Base URL for accessing media files (must match app.add_media_files setup)
MEDIA_BASE_URL = '/media'



# If you don't want to add unidecode as a dependency,
# you can use a simpler ASCII-only cleaning function.

def _format_wled_filename(original_filename: str) -> str:
    """
    Formats a filename to be WLED-compatible:
    - Transliterates to ASCII using unidecode.
    - Replaces common problematic characters.
    - Ensures the name (without extension) is not too long (WLED limit is 32 chars total).
    """
    try:
        # Transliterate to ASCII
        name_part, ext_part = os.path.splitext(original_filename)
        ascii_name = unidecode(name_part)
    except Exception as e:
        # Fallback if unidecode fails or is not available
        page_logger.warning(f"Unidecode failed for '{original_filename}': {e}. Using basic cleaning.")
        name_part, ext_part = os.path.splitext(original_filename)
        ascii_name = name_part

    # Replace spaces and common problematic characters
    cleaned_name = re.sub(r'[^\w.-]', '_', ascii_name) # Allow A-Z, a-z, 0-9, '.', '-', '_'
    cleaned_name = cleaned_name.replace('__', '_') # Consolidate multiple underscores

    # WLED filenames (including extension) should be <= 31 characters (plus leading /g/)
    # Let's aim for a base name length that allows for a typical extension like ".gif"
    max_base_len = 31 - (len(ext_part) if ext_part else 0)
    if max_base_len < 1: # Handle very long extensions
        max_base_len = 1

    if len(cleaned_name) > max_base_len:
        cleaned_name = cleaned_name[:max_base_len]

    return cleaned_name + ext_part

async def robust_upload_gif_to_wled(
    wled_ip: str,
    local_gif_path: Path,
    logger: page_logger,
    notify_callback: callable = None  # Optional callback for UI notifications
) -> bool:
    """
    Robustly uploads a GIF file to a WLED device.

    Args:
        wled_ip: IP address of the WLED device.
        local_gif_path: Path object for the local GIF file.
        logger: Logger instance for logging messages.
        notify_callback: Optional callable (e.g., ui.notify) for user feedback.

    Returns:
        True if upload was successful, False otherwise.
    """

    if not local_gif_path.exists() or not local_gif_path.is_file():
        logger.error(f"Local GIF file not found: {local_gif_path}")
        if notify_callback:
            notify_callback(f"GIF file not found: {local_gif_path.name}", type='negative')
        return False

    formatted_filename = _format_wled_filename(local_gif_path.name)
    logger.info(f"Formatted WLED filename: {formatted_filename}")

    # 1. Get WLED info for filesystem space check
    wled_client = WLED(wled_ip)
    try:
        await wled_client.update() # Fetches /json/info
        if not wled_client.info or "fs" not in wled_client.info:
            logger.error(f"Could not retrieve filesystem info from WLED device {wled_ip}.")
            if notify_callback:
                notify_callback(f"WLED FS Info Error for {wled_ip}", type='negative')
            return False

        fs_info = wled_client.info["fs"]
        total_space_kb = fs_info.get("t", 0)
        used_space_kb = fs_info.get("u", 0)
        free_space_kb = total_space_kb - used_space_kb
        gif_size_kb = local_gif_path.stat().st_size / 1024

        logger.debug(f"WLED {wled_ip} - Free space: {free_space_kb:.2f} KB, GIF size: {gif_size_kb:.2f} KB")

        if gif_size_kb > free_space_kb:
            logger.error(
                f"Not enough space on WLED device {wled_ip}. "
                f"Required: {gif_size_kb:.2f} KB, Available: {free_space_kb:.2f} KB"
            )
            if notify_callback:
                notify_callback(
                    f"No space on WLED {wled_ip}. Need {gif_size_kb:.2f}KB, have {free_space_kb:.2f}KB",
                    type='negative'
                )
            return False

    except (WLEDConnectionError, WLEDError) as e:
        logger.error(f"Error connecting to WLED {wled_ip} for info: {e}")
        if notify_callback:
            notify_callback(f"WLED Connection Error (Info): {e}", type='negative')
        return False
    except Exception as e:
        logger.error(f"Unexpected error getting WLED info from {wled_ip}: {e}", exc_info=True)
        if notify_callback:
            notify_callback(f"WLED Info Error: {e}", type='negative')
        return False
    finally:
        # Ensure the WLED client session is closed if it was opened
        # The wled library's WLED object manages its own session with httpx
        # and closes it on garbage collection or explicitly with await wled_client.close()
        # For short-lived operations like this, explicit close might not be strictly necessary
        # but can be good practice if the client object were to be reused.
        # await wled_client.close() # httpx client used by wled lib is closed on __del__
        pass


    # 2. Upload the file using aiohttp
    # WLED expects uploads for GIF effect to be in /g/ directory.
    upload_url = f"http://{wled_ip}/edit?path=/g/"
    form_data = aiohttp.FormData()
    try:
        form_data.add_field(
            'file',
            local_gif_path.read_bytes(),
            filename=formatted_filename, # Use the WLED-formatted filename
            content_type='image/gif'
        )
    except IOError as e:
        logger.error(f"Error reading GIF file {local_gif_path}: {e}")
        if notify_callback:
            notify_callback(f"Error reading GIF: {e}", type='negative')
        return False

    logger.info(f"Attempting to upload '{formatted_filename}' to {wled_ip} at {upload_url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url, data=form_data, timeout=aiohttp.ClientTimeout(total=60)) as response:
                # WLED often returns 302 (redirect) or 200 on successful upload
                if response.status in [200, 302]:
                    logger.info(f"Successfully uploaded '{formatted_filename}' to {wled_ip}.")
                    if notify_callback:
                        notify_callback(f"Uploaded {formatted_filename} to WLED!", type='positive')
                    return True
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Failed to upload GIF to WLED {wled_ip}: {response.status} - {error_text}"
                    )
                    if notify_callback:
                        notify_callback(f"WLED Upload Error: {response.status}", type='negative')
                    return False
    except aiohttp.ClientError as e:
        logger.error(f"aiohttp.ClientError during GIF upload to {wled_ip}: {e}", exc_info=True)
        if notify_callback:
            notify_callback(f"Network Error Uploading: {e}", type='negative')
        return False
    except asyncio.TimeoutError:
        logger.error(f"Timeout during GIF upload to {wled_ip}.")
        if notify_callback:
            notify_callback(f"Upload Timeout to {wled_ip}", type='negative')
        return False
    except Exception as e:
        logger.error(f"Unexpected exception during GIF upload to {wled_ip}: {e}", exc_info=True)
        if notify_callback:
            notify_callback(f"GIF Upload Exception: {e}", type='negative')
        return False



# --- WLED Interaction Functions ---

async def get_wled_info(wled_ip: str) -> dict | None:
    """Fetches general information from WLED, including LED count, using the wled module."""
    try:
        # Instantiate the WLED client
        led = WLED(wled_ip)
        # Update the client state, which fetches /json/info and other data
        await led.update()
        # Return the info dictionary
        return led.info
    except WLEDConnectionError as e:
        page_logger.error(f"WLED connection error for {wled_ip}: {e}")
        ui.notify(f"WLED Connection Error: {e}", type='negative')
        return None
    except WLEDError as e:
        page_logger.error(f"WLED API error for {wled_ip}: {e}")
        ui.notify(f"WLED API Error: {e}", type='negative')
        return None
    except Exception as e:
        page_logger.error(f"Unexpected exception getting WLED info from {wled_ip}: {e}")
        ui.notify(f"Unexpected Error: {e}", type='negative')
        return None


async def upload_gif_to_wled_fs(wled_ip: str, local_gif_path: Path) -> bool:
    """
    Uploads a GIF to WLED's filesystem using aiohttp.
    The 'wled' module does not have a high-level method for filesystem uploads (/edit endpoint).
    """
    gif_filename = local_gif_path.name
    # WLED expects uploads for GIF effect to be in /g/ directory.
    # The path in the upload request should be the directory.
    # WLED uses the filename from the uploaded file part.
    upload_url = f"http://{wled_ip}/edit?path=/g/"

    form_data = aiohttp.FormData()
    form_data.add_field(
        'file',  # WLED's handleUpload expects a part named 'file' or 'data'
        local_gif_path.read_bytes(),
        filename=gif_filename,
        content_type='image/gif'
    )
    page_logger.info(f"Attempting to upload {gif_filename} to {wled_ip} at {upload_url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url, data=form_data) as response:
                # WLED often returns 302 (redirect) or 200 on successful upload
                if response.status in [200, 302]:
                    page_logger.info(f"Successfully uploaded {gif_filename} to {wled_ip}.")
                    return True
                else:
                    error_text = await response.text()
                    page_logger.error(f"Failed to upload GIF to WLED {wled_ip}: {response.status} - {error_text}")
                    ui.notify(f"WLED GIF Upload Error: {response.status}", type='negative')
                    return False
    except Exception as e:
        page_logger.error(f"Exception during GIF upload to {wled_ip}: {e}")
        ui.notify(f"GIF Upload Exception: {e}", type='negative')
        return False


async def create_gif_preset_on_wled(wled_ip: str, gif_filename: str, preset_name: str, led_count: int) -> bool:
    """Creates a preset on WLED to play the specified GIF using the wled module."""
    try:
        # Instantiate the WLED client
        led = WLED(wled_ip)

        # Construct the segment for the GIF effect (FX_MODE_FILE_GIF = 116)
        gif_segment = {
            "id": 0, "start": 0, "stop": led_count, "grp": 1, "spc": 0, "on": True, "bri": 255,
            "col": [[255, 255, 255], [0, 0, 0], [0, 0, 0]],  # Default colors
            "fx": 116,  # Effect ID for "File GIF"
            "sx": 100, "ix": 100,  # Default speed and intensity
            "pal": 0, "sel": True, "rev": False, "mi": False,
            "file": gif_filename  # Just the filename, WLED prepends /g/
        }

        # State to apply to WLED to activate the GIF
        state_to_activate_gif = {
            "on": True,
            "bri": 128,  # Overall brightness for the preset
            "seg": [gif_segment]
        }

        # 1. Apply the state to make the GIF active
        page_logger.info(f"Applying GIF state to WLED {wled_ip}...")
        apply_response = await led.state(state_to_activate_gif)
        if not apply_response.get("success"):
            page_logger.error(f"WLED apply state command failed: {apply_response}")
            ui.notify(f"WLED Apply State Failed: {apply_response.get('error', 'Unknown')}", type='negative')
            return False
        page_logger.info(f"GIF state applied to WLED {wled_ip}.")

        # 2. Save the current state as a new preset
        # `psave=255` saves to the next available preset slot.
        save_preset_payload = {
            "psave": 255,
            "n": preset_name,
            "ql": preset_name[:2]  # Quick load label (first 2 chars)
        }
        page_logger.info(f"Saving preset '{preset_name}' on WLED {wled_ip}...")
        save_response = await led.state(save_preset_payload)

        if save_response.get("success"):
            page_logger.info(f"Preset '{preset_name}' successfully saved to WLED {wled_ip}.")
            return True
        else:
            page_logger.error(f"WLED preset save command failed: {save_response}")
            ui.notify(f"WLED Preset Save Failed: {save_response.get('error', 'Unknown')}", type='negative')
            return False

    except WLEDConnectionError as e:
        page_logger.error(f"WLED connection error for {wled_ip}: {e}")
        ui.notify(f"WLED Connection Error: {e}", type='negative')
        return False
    except WLEDError as e:
        page_logger.error(f"WLED API error for {wled_ip}: {e}")
        ui.notify(f"WLED API Error: {e}", type='negative')
        return False
    except Exception as e:
        page_logger.error(f"Unexpected exception during WLED preset creation on {wled_ip}: {e}")
        ui.notify(f"WLED Preset Creation Exception: {e}", type='negative')
        return False


# --- NiceGUI Page Definition ---

@ui.page('/gif_manager')  # Define the route for this page
async def gif_manager_page():
    # Attempt to get WLED IP from Media object if available, otherwise use a default or leave empty
    default_wled_ip = cfg_mgr.media_config.get('host', "192.168.1.100") if cfg_mgr.media_config else "192.168.1.100"

    ui.label('WLED GIF Manager').classes('text-h4 self-center mb-4')

    wled_ip_input = ui.input(
        label='WLED IP Address',
        value=default_wled_ip
    ).classes('w-full md:w-1/2 self-center mb-4')

    gif_files_on_disk = []
    if GIF_DIR_PATH.exists() and GIF_DIR_PATH.is_dir():
        gif_files_on_disk = sorted([
            f for f in GIF_DIR_PATH.iterdir()
            if f.is_file() and f.suffix.lower() == '.gif'
        ])

    if not gif_files_on_disk:
        ui.label(f'No GIFs found in {GIF_DIR_PATH}.').classes('self-center text-warning')
        return

    ui.label(f'Found {len(gif_files_on_disk)} GIFs:').classes('text-lg self-center mb-2')

    async def handle_gif_click(gif_local_path: Path):
        """Shows a dialog to confirm upload and preset creation."""
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Manage GIF: {gif_local_path.name}').classes('text-xl font-semibold')
            preset_name_suggestion = gif_local_path.stem  # Use filename without extension as preset name
            preset_name_field = ui.input(label='Preset Name on WLED', value=preset_name_suggestion)

            async def do_upload_and_create_preset():
                wled_ip = wled_ip_input.value
                preset_name = preset_name_field.value

                if not wled_ip or not preset_name:
                    ui.notify('WLED IP and Preset Name are required.', type='negative')
                    return

                dialog.close()  # Close dialog before starting potentially long operations
                ui.notify(f'Processing {gif_local_path.name} for {wled_ip}...', spinner=True,
                          timeout=None)  # Indefinite spinner

                # 1. Get WLED Info (for LED count)
                wled_info = await get_wled_info(wled_ip)
                if not wled_info or "leds" not in wled_info or "count" not in wled_info["leds"]:
                    ui.notify(f"Could not retrieve LED count from {wled_ip}. Aborting.", type='negative')
                    ui.notify(close=True)  # Close spinner
                    return
                led_count = wled_info["leds"]["count"]

                # 2. Upload GIF
                upload_success = await upload_gif_to_wled_fs(wled_ip, gif_local_path)
                if not upload_success:
                    ui.notify(f"GIF upload failed for {gif_local_path.name}.", type='negative')
                    ui.notify(close=True)  # Close spinner
                    return

                # 3. Create Preset
                preset_success = await create_gif_preset_on_wled(wled_ip, gif_local_path.name, preset_name, led_count)
                ui.notify(close=True)  # Close spinner
                if preset_success:
                    ui.notify(f'Successfully processed {gif_local_path.name} for WLED!', type='positive')
                else:
                    ui.notify(f'Preset creation failed for {gif_local_path.name}. GIF might be uploaded.',
                              type='warning')

            with ui.row().classes('w-full justify-end mt-4 space-x-2'):
                ui.button('Cancel', on_click=dialog.close, color='slate')
                ui.button('Upload & Create Preset', on_click=do_upload_and_create_preset, color='primary')
        dialog.open()

    with ui.grid(columns='repeat(auto-fill, minmax(150px, 1fr))').classes('w-full gap-4 p-4'):
        for gif_path in gif_files_on_disk:
            # Construct URL for the GIF. Assumes 'media' is served at MEDIA_BASE_URL
            # and GIF_SUBDIR is under 'media'.
            gif_url = f"{MEDIA_BASE_URL}/{GIF_SUBDIR}/{gif_path.name}"

            with ui.card().tight().classes('cursor-pointer hover:shadow-xl transition-shadow'):
                ui.image(gif_url).classes('w-full h-40 object-contain bg-gray-200') \
                    .on('click', lambda p=gif_path: handle_gif_click(p)) \
                    .tooltip(f"Click to manage {gif_path.name}")
                ui.label(gif_path.name).classes('text-center p-2 text-sm truncate')

# To integrate this page:
# 1. Save this file (e.g., as src/gui/gif_manager_page.py)
# 2. In your main application file (e.g., mainapp.py or WLEDVideoSync.py):
#    from src.gui import gif_manager_page  # Ensure this module is imported
# 3. Add a way to navigate to it, e.g., in niceutils.py in your head_menu:
#    ui.button('GIF Manager', on_click=lambda: ui.navigate.to('/gif_manager'))
# 4. Ensure 'wled' and 'aiohttp' are in your requirements.txt
