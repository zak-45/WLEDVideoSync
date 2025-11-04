"""
a: zak-45
d: 08/10/2025
v: 1.0.0

This file creates a NiceGUI page for dynamically managing the WLEDVideoSync.ini configuration file.
It reads the INI file, parses the associated README for tooltips, and generates a user-friendly
interface for editing and saving settings.
"""
import configparser
from nicegui import ui
from configmanager import cfg_mgr


def parse_readme(readme_path):
    """
    Parses the WLEDVideoSync.readme file to extract tooltips for configuration settings.

    Args:
        readme_path (str): The path to the readme file.

    Returns:
        dict: A nested dictionary with tooltips structured as {section: {key: tooltip}}.
    """
    tooltips = {}
    current_section = None
    current_key = None
    try:
        with open(readme_path, 'r') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line.startswith('[') and stripped_line.endswith(']'):
                    current_section = stripped_line[1:-1]
                    tooltips[current_section] = {}
                    current_key = None
                elif stripped_line.startswith('#'):
                    line_content = stripped_line.lstrip('#').strip()
                    if ':' in line_content:
                        parts = line_content.split(':', 1)
                        key = parts[0].strip()
                        description = parts[1].strip()
                        if current_section:
                            tooltips[current_section][key] = description
                            current_key = key
                    elif current_key and current_section and line_content:
                        # Append multi-line descriptions
                        tooltips[current_section][current_key] += f' {line_content}'
                else:
                    current_key = None
    except FileNotFoundError:
        print(f"Warning: Readme file not found at {readme_path}")
    return tooltips


async def create_config_page():
    """
    Creates the NiceGUI page for editing the WLEDVideoSync.ini configuration.
    """
    # Load tooltips from the readme file
    readme_path = cfg_mgr.app_root_path('config/WLEDVideoSync.readme')
    tooltips = parse_readme(readme_path)

    # Load the current configuration
    config = configparser.ConfigParser(interpolation=None)
    config_path = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')
    config.read(config_path)

    # Dictionary to hold the UI input elements
    ui_elements = {}

    def save_config():
        """
        Gathers values from the UI and saves them to the INI file.
        """
        for c_section, items in ui_elements.items():
            for c_key, c_element in items.items():
                config.set(c_section, c_key, str(c_element.value))

        with open(config_path, 'w') as configfile:
            config.write(configfile)

        ui.notify('Configuration saved. You need to restart the application to apply changes...', type='positive')

    ui.label('WLEDVideoSync Configuration').classes('text-2xl self-center')
    ui.label('Modify settings and click "Save Configuration" to apply changes.').classes('self-center text-sm text-gray-500')

    # Create UI for each section in the config
    for section in config.sections():
        ui_elements[section] = {}
        with ui.expansion(section.capitalize(), icon='settings').classes('w-full'):
            with ui.grid(columns=2).classes('gap-4 w-full'):
                for key, value in config.items(section):
                    tooltip_text = tooltips.get(section, {}).get(key, f'Setting for {key}')

                    # Heuristic to determine the best UI element type
                    if value.lower() in ['true', 'false']:
                        # Use a switch for boolean values
                        element = ui.switch(text=key, value=(value.lower() == 'true'))
                    elif key == 'server_port' and value == 'auto':
                        # Special case for server_port with 'auto'
                        element = ui.input(label=key, value=value)
                    elif key == 'uvicorn_logging_level':
                        # Use a select for log levels
                        opts = ['debug', 'info', 'warning', 'error', 'critical', 'trace']
                        element = ui.select(options=opts, label=key, value=value.lower())
                    elif 'color' in key or value.startswith('#'):
                        # Use a color picker for color values
                        element = ui.color_input(label=key, value=value)
                    else:
                        # Default to a text input
                        element = ui.input(label=key, value=value)

                    element.tooltip(tooltip_text).classes('w-full')
                    ui_elements[section][key] = element

    ui.button('Save Configuration', on_click=save_config).classes('mt-4 self-center bg-blue-500 text-white')
