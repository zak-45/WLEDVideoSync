"""
a:zak-45
d:20/12/2024
v:1.0.0

Manages configuration settings for the application across different environments.

"""


import os
import logging
import subprocess
import sys
import cfg_load as app_cfg
import concurrent_log_handler
import psutil

import contextlib
from logging import config
from str2bool import str2bool

def root_path(filename):
    """
    Determines the root path of the application based on whether it's running from a compiled binary or in development mode.
    Returns the appropriate root path for accessing application resources, handling different OS structures.

    Args:
        filename (str): The name of the file or directory relative to the application's root.

    Returns:
        str: The absolute path to the specified file or directory.

    Examples:
        >> root_path('data/config.ini')
        '/path/to/app/data/config.ini'

    Handles different execution environments (compiled vs. development) to ensure consistent resource access.
    """

    if getattr(sys, 'frozen', False):  # Running from a compiled binary (Nuitka, PyInstaller)
        if sys.platform == "darwin":  # macOS with APP
            base_path = os.path.dirname(os.path.dirname(sys.argv[0]))  # Contents/
            return os.path.join(base_path, "MacOS", filename)
        else:  # Windows/Linux (Nuitka puts files in the same dir as the binary)
            base_path = os.path.dirname(sys.argv[0])
            return os.path.join(base_path, filename)

    # Running in development mode (not compiled)
    return os.path.join(os.path.dirname(__file__),filename)


def count_processes_by_name(name):
    """
    Counts the number of running processes with a given name.
    Iterates through all active processes and checks if their name matches the provided name.

    Args:
        name (str): The name of the process to count.

    Returns:
        int: The number of processes with the specified name.

    Examples:
        >> count = count_processes_by_name('chrome')
        >> print(f"Number of Chrome processes: {count}")

    Provides a utility function to monitor the number of instances of a specific process running on the system.
    """
    return sum(
        name in proc.info['name']
        for proc in psutil.process_iter(attrs=['name'])
        if proc.info['name']  # Avoid NoneType errors
    )

def run_window_msg(msg: str = '', msg_type: str = 'info'):
    """
    Displays a custom message using an external info window executable across different platforms.
    Launches a separate process to show an error or informational message in a platform-specific manner.

    Args:
        msg (str): The message text to be displayed.
        msg_type (str, optional): The type of message, defaults to 'info'.
        Can specify message type like 'info' or 'error'. If error, bg is 'red'

    Examples:
        >> run_window_msg("Operation completed successfully")
        >> run_window_msg("Error occurred", msg_type='error')

    In case of error, just bypass.
    """
    # window_info full path
    absolute_file_name = info_window_exe_name()
    # number of already running processes
    process_count = count_processes_by_name("info_window")

    # in case of many errors, we stop display error window after 15 processes found
    # safeguard to not take all OS resources
    if process_count < 15:
        with contextlib.suppress(Exception):
            command = (
                [absolute_file_name, msg, msg_type]
                if sys.platform.lower() == "win32"
                else [absolute_file_name, msg, msg_type, '&']
            )
            # Call the separate script to show the error/info message in a Tkinter window
            subprocess.Popen(command)

def info_window_exe_name():
    """
    Determines the appropriate executable name for displaying information windows based on the current operating system.
    Returns the platform-specific executable path for the info window utility.

    Returns:
        str: The filename of the info window executable for the current platform.
        Returns None if the platform is not recognized.

    Examples:
        >> info_window_exe_name()
        'xtra/info_window.exe'  # On Windows
        >> info_window_exe_name()
        'xtra/info_window.bin'  # On Linux

    """
    if sys.platform.lower() == 'win32':
        return ConfigManager.app_root_path('xtra/info_window.exe')
    elif sys.platform.lower() == 'linux':
        return ConfigManager.app_root_path('xtra/info_window')
    elif sys.platform.lower() == 'darwin':
        return ConfigManager.app_root_path('xtra/info_window')
    else:
        return None


class CustomLogger(logging.Logger):
    """
    A custom logging class that extends the standard Python Logger to display error messages
    in a custom window before logging. Enhances standard error logging by adding a visual notification mechanism.

    The CustomLogger overrides the standard error logging method to first display an error message
    in a separate window using run_window_msg(), and then proceeds with standard error logging.
    This provides an additional layer of user notification for critical log events.

    Methods:
        error: Overrides the standard error logging method to display a custom error message before logging.

    Examples:
        >> logger = CustomLogger('my_logger')
        >> logger.error('Critical system failure')  # Displays error in custom window and logs

    """
    def error(self, msg, *args, **kwargs):
        # Custom action before logging the error
        run_window_msg(str(msg), 'error')
        super().error(msg, *args, **kwargs)


class ConfigManager:
    """
    Manages configuration settings for the application across different environments.
    This class handles configuration initialization, logging setup, and provides access to various configuration sections.

    Attributes:
        logger: Configured logger instance for the application.
        server_config: Configuration settings related to server parameters.
        app_config: General application configuration settings.
        color_config: Color-related configuration settings.
        custom_config: Custom configuration parameters.
        logging_config_path: Path to the logging configuration file.
        logger_name: Name of the logger to be used.

    The configuration management supports both standard and one-file executable environments,
    ensuring flexible configuration loading and logging setup.

    # Usage
    config_manager = ConfigManager(logging_config_path='path/to/logging.ini', logger_name='CustomLoggerName')

    """

    def __init__(self, config_file='config/WLEDVideoSync.ini', logging_config_path='config/logging.ini', logger_name='WLEDLogger'):
        """
        Initializes the configuration manager with default or specified logging configuration settings.
        Sets up initial configuration attributes and prepares for configuration loading.

        Args:
            logging_config_path (str, optional): Path to the logging configuration file. Defaults to 'config/logging.ini'.
            logger_name (str, optional): Name of the logger to be used. Defaults to 'WLEDLogger'.

        The method initializes configuration-related attributes to None and sets the provided logging configuration path
        and logger name. It then calls the initialize method to set up the configuration based on the current environment.
        """
        self.manager_config = None
        self.logger = None
        self.server_config = None
        self.app_config = None
        self.color_config = None
        self.custom_config = None
        self.preset_config = None
        self.desktop_config = None
        self.ws_config = None
        self.text_config = None
        self.logging_config_path = self.app_root_path(logging_config_path)
        self.config_file = self.app_root_path(config_file)
        self.logger_name = logger_name
        self.initialize()

    @staticmethod
    def app_root_path(file):
        """
        Provides a static method to access the root path of the application.
        This method simply calls the root_path function to determine the application's root directory.

        Args:
            file (str): The name of the file or directory relative to the application's root.

        Returns:
            str: The absolute path to the specified file or directory.

        Examples:
            >> ConfigManager.app_root_path('data/config.ini')
            '/path/to/app/data/config.ini'

        This static method provides a convenient way to access the root_path functionality within the ConfigManager class.
        """
        return root_path(file)

    def initialize(self):
        """
        When this env var exists, this means running from the one-file compressed executable.
        This env does not exist when running from the extracted program.
        Expected way to work.
        We initialize only if running from the main compiled program.
        """
        if "NUITKA_ONEFILE_PARENT" not in os.environ:
            self.setup()

    def setup(self):
        """
        Configures the logging system and loads various configuration sections for the application.
        This method sets up the logger and populates configuration attributes with settings from the configuration file.

        The method performs the following key actions:
        - Initializes the logger using the specified configuration path and logger name
        - Reads the configuration file
        - Assigns configuration sections to specific attributes for easy access
        - Provides a centralized method for setting up application configurations

        The configuration sections include server settings, application parameters, color configurations,
        and custom settings, making them readily available throughout the application.
        """

        # read config
        # load config file
        cast_config =self.read_config()

        if cast_config is not None:
            # config keys
            self.server_config = cast_config[0]  # server key
            self.app_config = cast_config[1]  # app key
            self.color_config = cast_config[2]  # colors key
            self.custom_config = cast_config[3]  # custom key
            self.preset_config = cast_config[4]  # presets key
            self.desktop_config = cast_config[5]  # desktop key
            self.ws_config = cast_config[6]  # websocket key
            self.text_config = cast_config[7]  # text anim key
            self.manager_config = cast_config[8]  # SL manager key

        else:
            if self.logger is not None:
                self.logger.debug('Config file not found')

        # create logger
        self.logger = self.setup_logging()


    def setup_logging(self):
        """
        Sets up the logging system for the application based on a configuration file or default settings.
        Configures logging handlers and formatters according to the specified configuration file, or falls back to basic
        configuration if the file is not found.

        Returns:
            logging.Logger: The configured logger instance.

        Examples:
            >> logger = config_manager.setup_logging()
            >> logger.info('Application started')

        Ensures that logging is properly configured, even if the specified configuration file is missing.
        """
        # Set the custom logger class
        logging.setLoggerClass(CustomLogger)

        # read the config file
        if os.path.exists(self.logging_config_path):

            logging.config.fileConfig(self.logging_config_path, disable_existing_loggers=False)
            # trick: use the same name for all modules, ui.log will receive message from alls
            if str2bool(self.app_config['log_to_main']):
                logger = logging.getLogger('WLEDLogger')
            else:
                logger = logging.getLogger(self.logger_name)
            # take basename from config file and add root_path + log ( from the config file we want only the name )
            # handler[0] should be stdout, handler[1] should be ConcurrentRotatingFileHandler
            logger.handlers[1].baseFilename=self.app_root_path(f"log/{os.path.basename(logger.handlers[1].baseFilename)}")
            logger.handlers[1].lockFilename=self.app_root_path(f"log/{os.path.basename(logger.handlers[1].lockFilename)}")
            logger.debug(f"Logging configured using {self.logging_config_path} for {self.logger_name}")

        else:

            # if not found config, set default param
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger(self.logger_name)
            logger.debug(f"Logging config file {self.logging_config_path} not found. Using basic configuration.")

        return logger


    def read_config(self):
        """
        Reads and parses the application's configuration file.
        Loads configuration data from the specified INI file and organizes it into separate dictionaries for different
        configuration sections.

        Returns:
            tuple: A tuple containing dictionaries for server, app, colors, custom, presets, desktop,
                    and websocket configurations.
            Returns None if the configuration file cannot be loaded or parsed.

        Examples:
            >> server_config, app_config, ..., ws_config = config_manager.read_config()

        Handles potential exceptions during file loading and returns None if any error occurs.
        """
        # load config file
        try:
            cast_config = app_cfg.load(self.config_file)
            # config keys
            server_config = cast_config.get('server')
            app_config = cast_config.get('app')
            colors_config = cast_config.get('colors')
            custom_config = cast_config.get('custom')
            preset_config = cast_config.get('presets')
            desktop_config = cast_config.get('desktop')
            ws_config = cast_config.get('ws')
            text_config = cast_config.get('text')
            manager_config = cast_config.get('shared-list')

            return (server_config,
                    app_config,
                    colors_config,
                    custom_config,
                    preset_config,
                    desktop_config,
                    ws_config,
                    text_config,
                    manager_config)

        except Exception as e:
            if self.logger is not None:
                self.logger.debug(f'Error : {e}')

            return None