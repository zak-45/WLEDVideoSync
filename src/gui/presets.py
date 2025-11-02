"""
a: za-45
d: 13/03/2024
v: 1.0.0

This file, presets.py, is responsible for managing the saving and loading of "presets" for two main functional areas
in the application: filter presets and cast presets.
These presets are configurations for classes (typically named 'Desktop' or 'Media') that can be saved to and
loaded from .ini files.
The file provides both interactive (GUI-based) and non-interactive (programmatic) mechanisms for handling these presets,
leveraging the NiceGUI library for user interface elements.

The file is structured into three main sections:

Filter Preset Manager: Handles saving/loading of filter-related settings.
Cast Preset Manager: Handles saving/loading of casting-related settings.
Common Utilities: Helper functions for type conversion when reading from .ini files.

Logging is integrated throughout for error handling and debugging.

Key Components
1. Filter Preset Manager
manage_filter_presets: Adds "save" and "load" preset buttons to the UI for filter presets.
save_filter_preset: Opens a dialog to save the current filter configuration to an .ini file.
    It serializes various filter parameters (e.g., RGB balance, scaling, flipping, filters, gamma, preview settings)
    from the class object.
load_filter_preset: Loads a filter preset from an .ini file and applies it to the class object.
    Supports both interactive (file picker dialog) and non-interactive (direct file load) modes.
apply_preset_filter (inner function): Applies the loaded preset values to the class object,
    handling type conversion and missing keys gracefully.

2. Cast Preset Manager
manage_cast_presets: Adds "save" and "load" preset buttons to the UI for cast presets.
save_cast_preset: Opens a dialog to save the current cast configuration to an .ini file.
    It serializes general, multicast, and (for Desktop) area-specific parameters.
load_cast_preset: Loads a cast preset from an .ini file and applies it to the class object, with support for
    both interactive and non-interactive modes.
apply_preset_cast (inner function): Applies the loaded cast preset values to the class object,
    with type conversion and error handling.

3. Common Utilities
str2bool_ini: Converts string values to boolean, using the str2bool utility.
str2intstr_ini: Attempts to convert a string to an integer, falling back to the original value if conversion fails.
str2list_ini: Safely evaluates a string as a Python literal (e.g., list), with error logging on failure.

4. Supporting Elements
LoggerManager and logging: Provides structured logging for error reporting and debugging.
NiceGUI Integration: Uses NiceGUI components (dialogs, buttons, notifications) for interactive user experiences.
Config Management: Uses configparser for .ini file operations and a custom cfg_load module for loading configurations.

Summary
This file is a central utility for managing user-configurable presets in the application,
enabling users to easily save and restore complex configurations for both filtering and casting operations.
It abstracts the details of file I/O, type conversion, and user interaction, providing a consistent and
robust interface for preset management within the larger system.

"""

import os
import traceback
import configparser
import contextlib
import ast
import cfg_load as cfg

from nicegui import ui
from str2bool import str2bool

from src.gui.niceutils import LocalFilePicker

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.presets')
presets_logger = logger_manager.logger


"""
Filter preset mgr
"""

async def manage_filter_presets(class_name, class_obj):
    """ Manage presets"""

    ui.button('save preset', on_click=lambda: save_filter_preset(class_name, class_obj)).classes('w-20')
    ui.button('load preset', on_click=lambda: load_filter_preset(class_name, class_obj)).classes('w-20')


async def save_filter_preset(class_name: str, class_obj = None) -> None:
    """
    Save the current filter preset to an ini file.

    Parameters:
    - class_name (str): The name of the class to save the preset for. Must be 'Desktop' or 'Media'.
    """

    async def save_file(f_name: str) -> None:
        if not f_name or not f_name.strip():
            ui.notify(f'Preset name could not be blank: {f_name}', type='negative')
            return

        f_name = cfg_mgr.app_root_path(f'config/presets/filter/{class_name}/{f_name}.ini')
        if os.path.isfile(f_name):
            ui.notify(f'Preset {f_name} already exists', type='warning')
            return

        try:
            preset = configparser.ConfigParser()

            preset['RGB'] = {
                'balance_r': str(class_obj.balance_r),
                'balance_g': str(class_obj.balance_g),
                'balance_b': str(class_obj.balance_b)
            }
            preset['SCALE'] = {
                'scale_width': str(class_obj.scale_width),
                'scale_height': str(class_obj.scale_height)
            }
            preset['FLIP'] = {
                'flip': str(class_obj.flip),
                'flip_vh': str(class_obj.flip_vh)
            }
            preset['FILTERS'] = {
                'saturation': str(class_obj.saturation),
                'brightness': str(class_obj.brightness),
                'contrast': str(class_obj.contrast),
                'sharpen': str(class_obj.sharpen)
            }
            preset['AUTO'] = {
                'auto_bright': str(class_obj.auto_bright),
                'clip_hist_percent': str(class_obj.clip_hist_percent)
            }
            preset['GAMMA'] = {
                'gamma': str(class_obj.gamma)
            }
            preset['PREVIEW'] = {
                'preview_top': str(class_obj.preview_top),
                'preview_w': str(class_obj.preview_w),
                'preview_h': str(class_obj.preview_h)
            }

            with open(f_name, 'w') as conf:
                preset.write(conf)

            dialog.close()
            ui.notify(f'Preset saved for {class_name} as {f_name}', type='info')
        except Exception as e:
            presets_logger.error(f'Error saving preset: {e}')
            ui.notify(f'Error saving preset: {e}', type='negative')

    with ui.dialog() as dialog:
        dialog.open()
        with ui.card():
            ui.label(f'Saving Preset for {class_name}').classes('self-center')
            ui.separator()
            file_name = ui.input('Enter name', placeholder='preset name')
            with ui.row():
                ui.button('OK', on_click=lambda: save_file(file_name.value))
                ui.button('Cancel', on_click=dialog.close)


async def load_filter_preset(class_name: str, class_obj: object = None, interactive: bool = True,
                             file_name: str = None) -> bool:
    """
    Load and apply a preset configuration for a given class.

    Parameters:
    - class_name (str): The name of the class to load the preset for. Must be 'Desktop' or 'Media'.
    - interactive (bool): Whether to run in interactive mode. Default is True.
    - file_name (str, optional): The name of the preset file to load in non-interactive mode.

    Returns:
    - bool: True if the preset was applied successfully, False otherwise.
    """
    if class_name not in ['Desktop', 'Media']:
        presets_logger.error(f'Unknown Class Name: {class_name}')
        return False

    async def apply_preset_filter(preset_data: dict):
        try:
            keys_to_check = [
                ('balance_r', 'RGB', 'balance_r', int),
                ('balance_g', 'RGB', 'balance_g', int),
                ('balance_b', 'RGB', 'balance_b', int),
                ('flip', 'FLIP', 'flip', str2bool_ini),
                ('flip_vh', 'FLIP', 'flip_vh', int),
                ('scale_width', 'SCALE', 'scale_width', int),
                ('scale_height', 'SCALE', 'scale_height', int),
                ('saturation', 'FILTERS', 'saturation', int),
                ('brightness', 'FILTERS', 'brightness', int),
                ('contrast', 'FILTERS', 'contrast', int),
                ('sharpen', 'FILTERS', 'sharpen', int),
                ('auto_bright', 'AUTO', 'auto_bright', str2bool_ini),
                ('clip_hist_percent', 'AUTO', 'clip_hist_percent', int),
                ('gamma', 'GAMMA', 'gamma', float),
                ('preview_top', 'PREVIEW', 'preview_top', str2bool_ini),
                ('preview_w', 'PREVIEW', 'preview_w', int),
                ('preview_h', 'PREVIEW', 'preview_h', int)
            ]

            for attr, section, key, *conversion in keys_to_check:
                try:
                    value = preset_data[section][key]
                    if conversion:
                        value = conversion[0](value)
                    setattr(class_obj, attr, value)
                except KeyError:
                    presets_logger.warning(f'Key {section}.{key} does not exist in the preset data')

            if interactive:
                ui.notify('Preset applied', type='info')
            return True

        except Exception as er:
            presets_logger.error(traceback.format_exc())
            presets_logger.error(f'Error applying preset: {er}')
            ui.notify('Error applying preset', type='negative', position='center')
            return False

    if interactive:
        with ui.dialog() as dialog:
            dialog.open()
            with ui.card().classes('self-center'):
                ui.label(f'{class_name} Preset').classes('self-center')
                ui.separator()
                result = await LocalFilePicker(directory=cfg_mgr.app_root_path(f'config/presets/filter/{class_name}'),
                                               multiple=False,
                                               thumbs=False)
                if result is not None:
                    preset_filter_data = cfg.load(result[0]).to_dict()
                    ui.label(f'Preset name: {result}')
                    with ui.expansion('See values'):
                        await ui.json_editor({'content': {'json': preset_filter_data}}) \
                            .run_editor_method('updateProps', {'readOnly': True})
                    with ui.row():
                        ui.button('Apply', on_click=lambda: apply_preset_filter(preset_filter_data))
                        ui.button('EXIT', on_click=dialog.close)
                    return True
                else:
                    ui.label('No preset selected')
                    return False

    else:

        try:
            preset_filter_data = cfg.load(cfg_mgr.app_root_path(f'config/presets/filter/{class_name}/{file_name}'))
            return await apply_preset_filter(preset_filter_data)

        except Exception as e:
            presets_logger.error(f'Error loading preset: {e}')
            return False


"""
END Filter preset mgr
"""

"""
Cast preset mgr
"""


def manage_cast_presets(class_name, class_obj):
    """ Manage presets"""
    ui.button('save preset', on_click=lambda: save_cast_preset(class_name, class_obj)).classes('w-20')
    ui.button('load preset', on_click=lambda: load_cast_preset(class_name, class_obj)).classes('w-20')


async def save_cast_preset(class_name: str, class_obj = None) -> None:
    """
    Save the current cast preset to an ini file.

    Parameters:
    - class_name (str): The name of the class to save the preset for. Must be 'Desktop' or 'Media'.
    """

    async def save_file(f_name: str) -> None:
        if not f_name or not f_name.strip():
            ui.notify(f'Preset name could not be blank: {f_name}', type='negative')
            return

        f_name = cfg_mgr.app_root_path(f'config/presets/cast/{class_name}/{f_name}.ini')
        if os.path.isfile(f_name):
            ui.notify(f'Preset {f_name} already exists', type='warning')
            return

        try:

            preset = configparser.ConfigParser()

            preset['GENERAL'] = {
                'rate': str(class_obj.rate),
                'preview': str(class_obj.preview),
                'stopcast': str(class_obj.stopcast),
                'scale_width': str(class_obj.scale_width),
                'scale_height': str(class_obj.scale_height),
                'wled': str(class_obj.wled),
                'wled_live': str(class_obj.wled_live),
                'host': str(class_obj.host),
                'viinput': str(class_obj.viinput)
            }

            preset['MULTICAST'] = {
                'multicast': str(class_obj.multicast),
                'cast_x': str(class_obj.cast_x),
                'cast_y': str(class_obj.cast_y),
                'cast_devices': str(class_obj.cast_devices)
            }

            if class_name == 'Desktop':
                preset['AREA'] = {
                    'monitor': str(class_obj.monitor_number),
                    'screen_coordinates': str(class_obj.screen_coordinates)
                }

            with open(f_name, 'w') as configfile:
                preset.write(configfile)

            dialog.close()
            ui.notify(f'Preset saved for {class_name} as {f_name}', type='info')
        except Exception as e:
            presets_logger.error(f'Error saving preset: {e}')
            ui.notify(f'Error saving preset: {e}', type='negative')

    with ui.dialog() as dialog:
        dialog.open()
        with ui.card():
            ui.label(f'Saving Preset for {class_name}').classes('self-center')
            ui.separator()
            file_name = ui.input('Enter name', placeholder='Preset name')

            with ui.row():
                ui.button('OK', on_click=lambda: save_file(file_name.value))
                ui.button('Cancel', on_click=dialog.close)


async def load_cast_preset(class_name: str, class_obj: object = None, interactive: bool = True,
                           file_name: str = None) -> bool:
    """
    Load and apply a cast preset configuration for a given class.

    Parameters:
    - class_name (str): The name of the class to load the preset for. Must be 'Desktop' or 'Media'.
    - interactive (bool): Whether to run in interactive mode. Default is True.
    - file_name (str, optional): The name of the preset file to load in non-interactive mode.

    Returns:
    - bool: True if the preset was applied successfully, False otherwise.
    """
    if class_name not in ['Desktop', 'Media']:
        presets_logger.error(f'Unknown Class Name: {class_name}')
        return False

    async def apply_preset_cast(preset_cast_data: dict):
        try:
            keys_to_check = [
                ('rate', 'GENERAL', 'rate', int),
                ('preview', 'GENERAL', 'preview', str2bool_ini),
                ('stopcast', 'GENERAL', 'stopcast', str2bool_ini),
                ('scale_width', 'GENERAL', 'scale_width', int),
                ('scale_height', 'GENERAL', 'scale_height', int),
                ('wled', 'GENERAL', 'wled', str2bool_ini),
                ('wled_live', 'GENERAL', 'wled_live', str2bool_ini),
                ('host', 'GENERAL', 'host'),
                ('viinput', 'GENERAL', 'viinput', str2intstr_ini),
                ('multicast', 'MULTICAST', 'multicast', str2bool_ini),
                ('cast_x', 'MULTICAST', 'cast_x', int),
                ('cast_y', 'MULTICAST', 'cast_y', int),
                ('cast_devices', 'MULTICAST', 'cast_devices', str2list_ini),
                ('monitor', 'AREA', 'monitor', int),
                ('screen_coordinates', 'AREA', 'screen_coordinates', str2list_ini)
            ]

            # specific keys for Desktop
            if class_name == 'Desktop':
                keys_to_check.append(('monitor', 'AREA', 'monitor', int))
                keys_to_check.append(('screen_coordinates', 'AREA', 'screen_coordinates', str2list_ini))

            # apply new value and only warn if not exist
            # conversion is done if necessary
            for attr, section, key, *conversion in keys_to_check:
                try:
                    value = preset_cast_data[section][key]
                    if conversion:
                        value = conversion[0](value)
                    setattr(class_obj, attr, value)
                except KeyError:
                    presets_logger.warning(f'Key {section}.{key} does not exist in the preset data')

            if interactive:
                ui.notify('Preset applied', type='info')
            return True

        except Exception as er:
            presets_logger.error(traceback.format_exc())
            presets_logger.error(f'Error applying preset: {er}')
            ui.notify('Error applying preset', type='negative', position='center')
            return False

    if interactive:
        with ui.dialog() as dialog:
            dialog.open()
            with ui.card().classes('self-center'):
                ui.label(f'{class_name} Preset').classes('self-center')
                ui.separator()
                result = await LocalFilePicker(directory=cfg_mgr.app_root_path(f'config/presets/cast/{class_name}'),
                                               multiple=False,
                                               thumbs=False)
                if result is not None:
                    preset_data = cfg.load(result[0]).to_dict()
                    ui.label(f'Preset name: {result}')
                    with ui.expansion('See values'):
                        await ui.json_editor({'content': {'json': preset_data}}) \
                            .run_editor_method('updateProps', {'readOnly': True})
                    with ui.row():
                        ui.button('Apply', on_click=lambda: apply_preset_cast(preset_data))
                        ui.button('EXIT', on_click=dialog.close)
                    return True
                else:
                    ui.label('No preset selected')
                    return False
    else:

        try:
            preset_data = cfg.load(cfg_mgr.app_root_path(f'config/presets/cast/{class_name}/{file_name}'))
            return await apply_preset_cast(preset_data)
        except Exception as e:
            presets_logger.error(f'Error loading preset: {e}')
            return False


"""
END Cast preset mgr
"""

"""
Common Preset utility
"""


def str2bool_ini(value: str) -> bool:
    """Convert a string value to a boolean using the str2bool utility.

    Returns True or False based on the string input, following standard boolean string conversions.

    Args:
        value (str): The string value to convert.

    Returns:
        bool: The converted boolean value.
    """
    return str2bool(value)


def str2intstr_ini(value: str):
    """Convert a string to an integer if possible, otherwise return the original value.

    Attempts to convert the input string to an integer, returning the original value if conversion fails.

    Args:
        value (str): The string value to convert.

    Returns:
        int or str: The converted integer value, or the original string if conversion fails.
    """
    with contextlib.suppress(Exception):
        value = int(value)
    return value


def str2list_ini(value: str):
    """Convert a string to a Python list using literal evaluation.

    Attempts to safely evaluate the input string as a Python literal,
    returning the resulting list or the original value if conversion fails.

    Args:
        value (str): The string value to convert.

    Returns:
        list or str: The converted list if successful, otherwise the original string.
    """
    try:
        value = ast.literal_eval(value)
    except Exception as e:
        presets_logger.warning(f'Not able to convert to list: {value} Error : {e}')
    return value


"""
END Common
"""
