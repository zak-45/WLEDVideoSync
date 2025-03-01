from nicegui import ui
import pkgutil
from importlib.metadata import metadata, PackageNotFoundError


def get_installed_modules():
    return sorted([module.name for module in pkgutil.iter_modules()])


def get_module_info(module_name):
    if not module_name.strip():
        return None

    try:
        meta = metadata(module_name)
        version = meta.get("Version", "Unknown")
        author = meta.get("Author", "Unknown")
    except PackageNotFoundError:
        version, author = "Unknown", "Unknown"

    return {
        "name": module_name,
        "version": version,
        "author": author
    }


def display_info():
    module_name = input_field.value.strip() or dropdown.value
    if not module_name:
        ui.notify("Please enter or select a module name.", color="red")
        return

    info = get_module_info(module_name)
    if not info:
        ui.notify(f"Module '{module_name}' not found.", color="red")
        return

    result_container.clear()

    with result_container:
        with ui.expansion("Module Info", value=True):
            ui.label(f"**Name:** {info['name']}")
            ui.label(f"**Version:** {info['version']}")
            ui.label(f"**Author:** {info['author']}")


ui.label("Python Module Explorer").classes("text-2xl font-bold")
input_field = ui.input("Enter module name")
dropdown = ui.select(get_installed_modules(), label="Select a module")
ui.button("Get Info", on_click=display_info)
result_container = ui.column()

ui.run()
