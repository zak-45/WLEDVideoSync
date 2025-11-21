# Compilation mode, standalone everywhere
# nuitka-project: --nofollow-import-to=doctest
# nuitka-project: --nofollow-import-to=matplotlib
# nuitka-project: --noinclude-default-mode=error
# nuitka-project: --include-raw-dir=xtra=xtra
# nuitka-project: --include-module=tkinter
# nuitka-project: --enable-plugin=tk-inter
# nuitka-project-if: {OS} == "Windows":
#   nuitka-project: --onefile-windows-splash-screen-image={MAIN_DIRECTORY}/splash-screen.png
#   nuitka-project: --include-module=winloop
#   nuitka-project: --windows-console-mode=attach
# nuitka-project-if: os.getenv("DEBUG_COMPILATION", "no") == "yes":
#   nuitka-project: --force-stdout-spec=WLEDVideoSync.out.txt
#   nuitka-project: --force-stderr-spec=WLEDVideoSync.err.txt
# nuitka-project-if: {OS} == "Linux":
#   nuitka-project: --enable-plugins=pyside6
#   nuitka-project: --static-libpython=yes
"""
a : zak-45
d : 07/04/2024
v : 1.0.0

Main WLEDVideoSync.

Overview
This Python script, WLEDVideoSync.py, is the main entry point for the WLEDVideoSync application. 
It uses the nicegui library to create a user interface for controlling WLED devices. 
The application supports different operating systems (Windows, Linux, macOS) and handles platform-specific configurations. 
It also manages a server for the UI and provides features like system tray integration. 
The script initializes settings, starts the GUI, and performs cleanup operations upon exit.

Key Components
Configuration Management (configmanager.ConfigManager): 
    Handles reading and writing application settings from the WLEDVideoSync.ini file. 
    This allows users to customize the application's behavior. 
    The cfg_mgr instance is used throughout the script to access configuration values.

Multiprocessing Setup (Utils.mp_setup): 
    Initializes multiprocessing components (Process and Queue) likely used for background tasks or communication.    

Platform-Specific Initialization (init_linux_win, linux_settings, init_darwin, init_common): 
    These functions handle OS-specific configurations, such as setting default parameters for the GUI, 
    handling file permissions, and setting up the system tray icon. 
    They ensure the application runs correctly on different platforms.

GUI Management (run_gui): 
    This function is the core of the UI setup. 
    It starts the nicegui server, configures static file serving, handles system tray integration using pystray, 
    and sets various GUI parameters like title, icon, and port. It also manages cleanup tasks when the GUI is closed.

CastAPI: 
    This module (not shown in the provided code) likely contains the core logic for interacting with WLED devices 
    and handling video synchronization. It's initialized on startup using app.on_startup(CastAPI.init_actions).

src.gui.niceutils: 
    This module provides custom utilities for the NiceGUI framework, including a custom OpenAPI implementation.

Nuitka Compilation Support: 
    The file includes several comments related to Nuitka compilation, 
    This project is designed to be compiled into a standalone executable.
    This improves performance and distribution.

Temporary File Handling: 
    The script uses temporary files (stored in a tmp directory) for inter-process communication, 
    specifically for sharing the server port between the main process and the system tray icon. 
    It also cleans up these temporary files on exit.

"""
import multiprocessing
import os

from subprocess import Popen

# Suppress the specific UserWarning from the 'fs' library about pkg_resources.
# This is a known issue with some dependencies and newer versions of setuptools.
# The warning is informational and does not affect the application's functionality.
import warnings
warnings.filterwarnings("ignore", category=UserWarning, message="pkg_resources is deprecated as an API")

if os.getenv('WLEDVideoSync_trace'):
    import tracetool

# import everything from mainapp.py: the main logic come from there
from mainapp import *

from src.gui.niceutils import custom_openapi

# disable not used costly import (from nicegui)
os.environ['MATPLOTLIB'] = 'false'

def cfg_settings(config_file, preview_subprocess, native_ui, native_size, first_run_os):
    """Update configuration settings based on OS and user preferences.

    This function updates specific keys in the configuration file related to the
    preview subprocess, native UI usage, UI size, and first-run status for
    different operating systems.

    Args:
        preview_subprocess (str): Whether to use a subprocess for preview.
        native_ui (str): Whether to use native UI elements.
        native_size (str): Size of the native UI window (if used).
        first_run_os (str): Key indicating the first run status for the OS.
        :param first_run_os:
        :param native_size:
        :param native_ui:
        :param preview_subprocess:
        :param config_file:
    """
    Utils.update_ini_key(config_file, 'app', 'preview_proc', preview_subprocess)
    Utils.update_ini_key(config_file, 'app', 'native_ui', native_ui)
    Utils.update_ini_key(config_file, 'app', 'native_ui_size', native_size)
    Utils.update_ini_key(config_file, 'app', first_run_os, 'False')
    Utils.update_ini_key(config_file, 'app', 'splash', 'True')
    Utils.update_ini_key(config_file, 'desktop', 'capture', 'av')

def init_linux_win():
    """Initialize settings for Linux and Windows platforms.

    This function applies default parameters and configurations specific to
    Linux and Windows operating systems, including GUI settings and
    platform-dependent initializations. It also initializes common settings
    and runs the tk initialization process.
    """

    config_file = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')

    # Apply some default params only once
    # Apply default GUI / param , depend on platform

    if PLATFORM == 'win32':
        cfg_settings(config_file,'False', 'True', '1200,720', 'win_first_run')
    elif PLATFORM == 'linux':
        linux_settings(config_file)
    else:
        main_logger.error(f'PLATFORM NOT MANAGED : {PLATFORM}')

    # common all OS
    init_common(config_file)


def linux_settings(config_file):
    """Apply Linux-specific settings and configurations.

    This function sets configuration parameters specific to Linux environments,
    including preview process settings and native UI settings. It also
    performs actions like setting file permissions and changing folder/app icons.
    
    These are no blocking actions...
    
    """
    cfg_settings(config_file,'True', 'False', '', 'linux_first_run')

    linux_cmd(
        "xtra/info_window",
        'chmod +x ',
        'info_window process : ',
        ' , path: ',
    )
    linux_cmd(
        "assets/custom_folder.png",
        'gio set -t string "WLEDVideoSync" metadata::custom-icon file://',
        'custom_folder process : ',
        ', path: ',
    )
    linux_cmd(
        "favicon.png",
        'gio set -t string "WLEDVideoSync/WLEDVideoSync-Linux_x86_64.bin" metadata::custom-icon file://',
        'app icon process : ',
        ', path: ',
    )


def linux_cmd(arg0, arg1, arg2, arg3):
    """Execute a Linux command for file or icon configuration.

    Runs a shell command using the provided arguments to perform actions such as changing file permissions or
    setting custom icons.
    Prints the process information and returns the command string.

    Args:
        arg0 (str): Path argument for the file or resource.
        arg1 (str): Command prefix (e.g., 'chmod +x ').
        arg2 (str): Description for process output.
        arg3 (str): Additional description for process output.

    Returns:
        str: The command string that was executed.
    """
    # chmod +x info window
    info_window = cfg_mgr.app_root_path(arg0)
    result = f'{arg1}{info_window}'
    proc1 = Popen([result], shell=True, stdin=None, stdout=None, stderr=None)
    print(f'{arg2}{proc1.pid}{arg3}{info_window}')

    return result

def init_darwin():
    """Initialize settings for Darwin (macOS) platform.

    This function applies default parameters and configurations specific to
    macOS, including preview process settings, native UI settings, and
    sets the 'mac_first_run' flag to False after the initial setup.

    These are no blocking actions...
        
    """

    config_file = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')

    Utils.update_ini_key(config_file, 'app', 'preview_proc', 'True')
    Utils.update_ini_key(config_file, 'app', 'native_ui', 'True')
    Utils.update_ini_key(config_file, 'app', 'native_ui_size', '1200,720')
    Utils.update_ini_key(config_file, 'app', 'mac_first_run', 'False')
    Utils.update_ini_key(config_file, 'app', 'splash', 'False')
    Utils.update_ini_key(config_file, 'desktop', 'capture', 'mss')

    # chmod +x info window
    cmd_str = f'chmod +x {cfg_mgr.app_root_path("xtra/info_window")}'
    proc = Popen([cmd_str], shell=True, stdin=None, stdout=None, stderr=None)
    print(f'info_window process : {proc.pid} for :{cmd_str}')

    # common all OS
    init_common(config_file)


def init_common(config_file):
    """Initialize common settings across all platforms.

    This function performs initialization tasks common to all operating systems,
    such as disabling YouTube features if yt-dlp is not installed, and
    setting flags for initialization completion and system tray usage.
    """
    # Apply YouTube settings if yt_dlp not imported
    if 'yt_dlp' not in sys.modules:
        Utils.update_ini_key(config_file, 'custom', 'yt_enabled', 'False')

    # global
    Utils.update_ini_key(config_file, 'app', 'init_config_done', 'True')
    Utils.update_ini_key(config_file, 'app', 'put_on_systray', 'False')
    Utils.update_ini_key(config_file, 'app', 'font_file', '')
    Utils.update_ini_key(config_file, 'custom', 'bg_image', '')

    # generate self signed cert
    from src.utl.self_signed_cert import generate_self_signed_cert

    generate_self_signed_cert(cfg_mgr.app_root_path('xtra/cert/cert.pem'),
                              cfg_mgr.app_root_path('xtra/cert/key.pem'),
                              Utils.get_local_ip_address())


def parse_native_ui_size(size_str):
    """Parse the native UI size string into a tuple of integers.

    Converts a comma-separated string representing the native UI window size into a tuple of two integers.
    Raises a ValueError if the format is invalid or does not contain exactly two values.

    Args:
        size_str (str): The native UI size as a comma-separated string (e.g., "800,600").

    Returns:
        tuple: A tuple containing two integers representing the width and height.

    Raises:
        ValueError: If the input string is not properly formatted or does not contain two values.
    """
    try:
        size_tuple = tuple(map(int, size_str.split(',')))
        if len(size_tuple) != 2:
            raise ValueError("native_ui_size must have two comma-separated integer values.")
        return size_tuple
    except Exception as er:
        raise ValueError(f"Invalid native_ui_size format: {size_str}") from er

def select_gui():
    """Select the appropriate GUI mode based on configuration.

    Determines whether to use a native GUI, a webview-based GUI, or no GUI
    (systray only) based on the application's configuration settings. Handles
    parsing and validation of native UI size from the configuration.

    Returns:
        tuple: A tuple containing the show flag (bool), native_ui flag (bool),
               and native_ui_size (tuple or None).
    """
    # choose GUI
    show = None
    native_ui = cfg_mgr.app_config['native_ui'] if cfg_mgr.app_config is not None else 'False'
    #
    if ((cfg_mgr.app_config is not None and cfg_mgr.app_config['native_ui_size'] == '')
             or (cfg_mgr.app_config is None)):
        native_ui_size = '800,600'
    else:
        native_ui_size = cfg_mgr.app_config['native_ui_size']

    try:
        if native_ui.lower() == 'none' or str2bool(cfg_mgr.app_config['put_on_systray']):
            native_ui_size = None
            native_ui = None
            show = False
        elif str2bool(native_ui):
            native_ui = True
            native_ui_size = parse_native_ui_size(native_ui_size)
        else:
            show = True
            native_ui_size = None
            native_ui = False
    except Exception as error:
        main_logger.error(f'Error in config file to select GUI from native_ui : {native_ui} - {error}')
        sys.exit(3)

    return show, native_ui, native_ui_size

def check_pystray():
    if str2bool(cfg_mgr.app_config['put_on_systray']):
        from src.gui.wledtray import WLEDVideoSync_systray

        if PLATFORM == 'linux':
            systray_backend = cfg_mgr.app_config['systray_backend'].lower()
            if systray_backend in ['appindicator', 'gtk', 'xorg']:

                os.environ["PYSTRAY_BACKEND"] = systray_backend
            else:
                main_logger.error(f'Bad value for systray_backend : {systray_backend}')
                sys.exit(5)

        # run systray in no blocking mode
        WLEDVideoSync_systray.run_detached()

def set_env():
    # set QT in linux if compiled version (let choice when run from source)
    if PLATFORM == 'linux' and (cfg_mgr.compiled() or str2bool(cfg_mgr.app_config['native_set_qt'])):
        os.environ["PYWEBVIEW_GUI"] = "qt"
    # Force software-based OpenGL rendering on Ubuntu
    if PLATFORM == 'linux' and str2bool(cfg_mgr.custom_config['libgl']):
        os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"

"""
MAIN Logic 
"""

# app settings set here to avoid problem with native if used, see: https://github.com/zauberzeug/nicegui/pull/4627
app.openapi = custom_openapi
app.add_static_files('/assets', cfg_mgr.app_root_path('assets'))
app.add_media_files('/media', cfg_mgr.app_root_path('media'))
app.add_static_files('/log', cfg_mgr.app_root_path('log'))
app.add_static_files('/config', cfg_mgr.app_root_path('config'))
app.add_static_files('/tmp', cfg_mgr.app_root_path('tmp'))
app.add_static_files('/xtra', cfg_mgr.app_root_path('xtra'))
app.on_startup(init_actions)
app.on_shutdown(cleanup_on_shutdown)


def main():
    """Run the main graphical user interface (GUI).

    This function initializes and runs the NiceGUI application, handling server
    configurations, system tray icon, GUI settings, and cleanup operations.
    """

    server_port = None
    server_ip = None

    print(f'Start WLEDVideoSync - NiceGui for : {PLATFORM}')

    if "NUITKA_ONEFILE_PARENT" not in os.environ and cfg_mgr.server_config is not None:
        server_ip, server_port = check_server()
        if server_ip is None or server_port is None:
            print('Exiting due to invalid server configuration.')
            main_logger.error('Exiting due to invalid server configuration.')
            main_logger.info('Application Terminated')
            sys.exit(4)

    """
    Pystray
    """
    check_pystray()

    """
    GUI
    """
    # set env vars
    set_env()

    # choose GUI
    show, native_ui, native_ui_size = select_gui()

    """
    splash screen
    """
    # show or not splash window
    if cfg_mgr.app_config is not None and str2bool(cfg_mgr.app_config['splash']) and native_ui != 'none':
        # Show splash screen in a separate thread to not block the main app
        # put in another process for macOS compatibility
        try:
            process, _ = Utils.mp_setup()
            splash_process = process(target=Utils.show_splash_screen)
            splash_process.daemon = True
            splash_process.start()
        except Exception as er:
            main_logger.error(f"Failed to launch splash process: {er}")

    """
    RUN
    """
    ui.run(title=f'WLEDVideoSync - {server_port}',
           favicon=cfg_mgr.app_root_path("favicon.ico"),
           host=server_ip,
           port=server_port,
           uvicorn_logging_level=cfg_mgr.server_config['uvicorn_logging_level'].lower(),
           fastapi_docs=str2bool(cfg_mgr.app_config['fastapi_docs'] if cfg_mgr.app_config is not None else 'True'),
           show=show,
           reconnect_timeout=int(
               cfg_mgr.server_config['reconnect_timeout'] if cfg_mgr.server_config is not None else '3'),
           reload=False,
           dark=dark,
           native=native_ui,
           window_size=native_ui_size,
           access_log=False,
           fullscreen=str2bool(cfg_mgr.app_config['fullscreen'] if cfg_mgr.app_config is not None else 'False'))

    """
    END
    """

    # stop pystray
    if str2bool(cfg_mgr.app_config['put_on_systray']):
        from src.gui.wledtray import WLEDVideoSync_systray
        from src.gui.wledtray import WLEDVideoSync_gui
        WLEDVideoSync_gui.close_all_webviews()
        WLEDVideoSync_systray.stop()

    print('End WLEDVideoSync - NiceGUI')

"""
Do not use if __name__ in {"__main__", "__mp_main__"}, made code reload with cpu_bound !!!!
"""
if __name__  == "__main__":
    # add multiprocessing support (not needed with Nuitka but for compatibility with other tools)
    multiprocessing.freeze_support()

    # Check for special command-line flags to run in a different mode.
    # set inter-process file name, dark mode
    status, args = Utils.handle_command_line_args(sys.argv)
    if not status:
        main_logger.error('argument parsing fails ')
        sys.exit(1)  # Exit if argument parsing fails
    # args
    file = args.file
    dark = args.dark

    # Dark Mode
    CastAPI.dark_mode = dark

    # Check for special command-line flags to run in a different mode.
    if ('--run-mobile-server' in sys.argv or
            '--run-sys-charts' in sys.argv or
            '--help' in sys.argv or
            '-h' in sys.argv
            ):

        # This block is executed ONLY when the app is launched as a child process
        # with the specific purpose of running the mobile camera server or system charts.
        if '--run-sys-charts' in sys.argv:

            try:
                main_logger.info('WLEDVideoSync -- Run System Charts process')
                import runcharts

                dev_list = asyncio.run(Utils.get_all_running_hosts(file))

                # this is a blocking call
                runcharts.main(dev_list, file, CastAPI.dark_mode)

            except Exception as e:
                main_logger.error(f'Error in run charts server : {e}')
                sys.exit(1)

            finally:
                sys.exit(0) # Exit cleanly when the server stops.

        elif '--run-mobile-server' in sys.argv :

            try:
                # 1. Initialize the desktop cast to create and read from a shared memory List.
                from src.cst import desktop
                from src.utl.utils import CASTUtils as Utils
                from src.utl.sharedlistmanager import SharedListManager
                from nicegui import native

                Desktop = desktop.CASTDesktop()
                Desktop.viinput = 'SharedList'
                Desktop.stopcast = False

                # define shared list manager
                sl_port = native.find_open_port(start_port=8800)
                sl_ip= '127.0.0.1'
                sl_manager = SharedListManager(sl_ip_address=sl_ip, sl_port=sl_port)
                sl_manager.start()
                # set it in Desktop
                Desktop.sl_manager = sl_manager

                # Check for special command-line flags to run in a different mode.
                # set Desktop Cast obj attributes
                status, args = Utils.handle_command_line_args(sys.argv, Desktop)
                if not status:
                    main_logger.error('argument parsing fails ')
                    sys.exit(1) # Exit if argument parsing fails

                # retrieve Media objects from other process
                # Shelve creates files with extensions like .dat, .bak, .dir , db depend on py version and platform
                file_to_check = Utils.get_shelve_file_path(file)
                # Check if the file exists
                if os.path.exists(file_to_check):
                    with shelve.open(file, "r") as proc_file:
                        media = proc_file.get("media") # Use .get for safer access
                    if media:
                        # update Desktop attributes from media attributes (have been copied into proc_file)
                        Desktop.set_from_obj(media)
                    else:
                        main_logger.warning("Inter-process Media object not found. Proceeding with default settings.")
                else:
                    main_logger.warning(f"Inter-process file {file_to_check} not found. Proceeding with default settings.")

                sl_thread = Desktop.cast()  # This creates the shared list and returns the handle

                # 2. Get necessary info for the mobile server.
                local_ip = Utils.get_local_ip_address()

                # 3. import mobile.
                import mobile

                main_logger.info('WLEDVideoSync -- Run mobile process')
                # 4. Start the mobile server. This is a blocking call.
                mobile.start_server(sl_thread.name, local_ip, CastAPI.dark_mode, sl_ip, sl_port)

            except Exception as e:
                main_logger.error(f'Error in mobile server : {e}')
                sys.exit(1)

            finally:
                sys.exit(0) # Exit cleanly when the server stops.

        else:

            main_logger.error(f'Unknown argument: {sys.argv}')
            sys.exit(2)


    else:

        # This is the main GUI application flow
        # --- Main Application Flow (if no special flags were found) ---

        # We check if executed from compressed version (linux & win)
        # instruct user to go to WLEDVideoSync folder to execute program and exit
        if "NUITKA_ONEFILE_PARENT" in os.environ:
            """
            When this env var exist, this mean run from the one-file compressed executable.
            This env not exist when run from the extracted program.
            Expected way to work.
            """
            init_linux_win()
            # run tk and close
            from src.gui.tkwininit import init
            init()
            sys.exit(0)

        elif PLATFORM == 'win32' and str2bool(cfg_mgr.app_config['win_first_run']):
            init_linux_win()
            # run tk and close
            from src.gui.tkwininit import init
            init()
            sys.exit(0)

        elif PLATFORM == 'linux' and str2bool(cfg_mgr.app_config['linux_first_run']):
            init_linux_win()
            # run tk and close
            from src.gui.tkwininit import init
            init()
            sys.exit(0)

        # On macOS (app), there is no "NUITKA_ONEFILE_PARENT" so we test on mac_first_run only
        # Update necessary params and exit
        if PLATFORM == 'darwin' and str2bool(cfg_mgr.app_config['mac_first_run']):
            init_darwin()
            # run tk and close
            from src.gui.tkmacinit import init
            init()
            sys.exit(0)

        # ------------------------------------------------------------------------------------------------------- #

        """
        Start infinite loop
        """
        main()

        """
        STOP
        """

        Utils.clean_tmp()

        main_logger.info('Application Terminated')
