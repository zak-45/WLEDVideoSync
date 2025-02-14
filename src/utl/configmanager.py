"""
a:zak-45
d:20/12/2024
v:1.0.0

Manages configuration settings for the application across different environments.

"""

from os import environ
from src.utl.utils import CASTUtils

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

    def __init__(self, logging_config_path='config/logging.ini', logger_name='WLEDLogger'):
        """
        Initializes the configuration manager with default or specified logging configuration settings.
        Sets up initial configuration attributes and prepares for configuration loading.

        Args:
            logging_config_path (str, optional): Path to the logging configuration file. Defaults to 'config/logging.ini'.
            logger_name (str, optional): Name of the logger to be used. Defaults to 'WLEDLogger'.

        The method initializes configuration-related attributes to None and sets the provided logging configuration path
        and logger name. It then calls the initialize method to set up the configuration based on the current environment.
        """
        self.logger = None
        self.server_config = None
        self.app_config = None
        self.color_config = None
        self.custom_config = None
        self.preset_config = None
        self.desktop_config = None
        self.ws_config = None
        self.logging_config_path = logging_config_path
        self.logger_name = logger_name
        self.initialize()

    def initialize(self):
        """
        When this env var exists, this means running from the one-file compressed executable.
        This env does not exist when running from the extracted program.
        Expected way to work.
        """
        if "NUITKA_ONEFILE_PARENT" not in environ:
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
        # create logger
        self.logger = CASTUtils.setup_logging(self.logging_config_path, self.logger_name)

        # load config file
        cast_config =CASTUtils.read_config()

        # config keys
        self.server_config = cast_config[0]  # server key
        self.app_config = cast_config[1]  # app key
        self.color_config = cast_config[2]  # colors key
        self.custom_config = cast_config[3]  # custom key
        self.preset_config = cast_config[4]  # presets key
        self.desktop_config = cast_config[5]  # desktop key
        self.ws_config = cast_config[6]  # websocket key