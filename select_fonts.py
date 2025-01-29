"""
a: zak-45
d: 29/01/2025
v: 1.0.0.0

This Python script uses the coldtype and nicegui libraries to create a simple graphical user interface (GUI)
for browsing and previewing system fonts.
The user can search for fonts, and hovering over a font name displays a preview image of the font rendered with sample
text. The font size for the preview is adjustable via a slider.

List all fonts available on the system
Generate a preview using coldtype 'skia image'

"""
import io
import base64
from coldtype import StSt
from coldtype.raster import *
from coldtype.text.reader import Font
from nicegui import ui

selected_font_path = None
selected_font_label = None

# Function to list all fonts using Coldtype
def get_system_fonts():
    """Retrieve a dictionary of system fonts.

    This function retrieves all available system fonts and returns them as a dictionary
    where keys are font stems and values are string representations of the font paths.
    Returns:
    dict: A dictionary mapping font stems to font paths.
    """
    fonts = Font.List('')  # Retrieve all available system fonts
    return {font.stem: str(font) for font in fonts}


# Function to generate a font preview using skia and coldtype
def generate_preview(font_path, preview_text="The quick brown fox jumps over the lazy dog"):
    """Generate a PNG preview image of a font.

    This function renders a given text string using the specified font and returns a byte stream
    containing the PNG image.  If the preview cannot be generated, it returns None.

    Args:
    font_path (str): The path to the font file.
        preview_text (str, optional): The text string to render. Defaults to "The quick brown fox jumps over the lazy dog".

    Returns:
        io.BytesIO | None: A byte stream containing the PNG image, or None if preview generation fails.
    """
    try:

        # Obtain the `skia.Image` directly by calling rasterized inline from coldtype
        font_rectangle = Rect(800, 100)
        font_image = (StSt(text=preview_text, font=font_path, font_size=s_font_size.value)
                      .align(font_rectangle)
                      .chain(rasterized(font_rectangle, wrapped=False)))  # Get skia.Image

        # Convert the image to a byte stream
        img_buffer = io.BytesIO()
        font_image.save(img_buffer, skia.kPNG)
        img_buffer.seek(0)
        return img_buffer

    except Exception as e:
        print(f"Could not generate preview: {e}")
        return None


# Prepare fonts
fonts = get_system_fonts()

# UI with NiceGUI
with (ui.column().classes('p-4 h-full') as layout):

    # function to filter fonts
    def filter_fonts(e):
        """Filter and display a list of fonts based on a user query.

        This function takes a query string and filters a list of available fonts, displaying
        matching font names in a UI element.  It also attaches mouseover, mouseout, and click
        event handlers to each displayed font name for preview and selection functionality.
        Args:
            e: The event object containing the user's query string.
        """

        query = e.value.lower()
        font_list.clear()
        for font_name in sorted(fonts.keys()):
            if query in font_name.lower():
                with font_list:
                    font_label = ui.label(font_name).classes("cursor-pointer hover:underline")
                    font_label.on(
                        "mouseover",
                        lambda font_name=font_name, font_label=font_label: show_preview(fonts[font_name], font_label)
                    )
                    font_label.on(
                        "mouseout",
                        lambda font_label=font_label: font_label.classes(remove='bg-slate-300')
                    )
                    font_label.on(
                        "click",
                        lambda font_label=font_label: ui.notify(f'Select font : {font_label}')
                    )

    ui.label("Hover over a font to see a preview").classes("text-sm font-bold mb-4")

    # Search bar
    search_input = ui.input(
        label="Search Fonts",
        placeholder="Type to search...",
        on_change=filter_fonts,
    ).classes("mb-4 w-full")

    # Searchable font list
    font_list = ui.column().classes('w-full flex-grow overflow-y-auto border rounded shadow p-2 bg-white max-h-[70vh]')

    preview_image = ui.image().classes("border rounded shadow mb-4").style(
        "width: 800px; height: 100px; background-color: white;")

    s_font_size = ui.slider(min=1, max=100, value=25, on_change=lambda var: show_preview(selected_font_path, selected_font_label))

    # Function to show preview
    def show_preview(font_path, font_label):
        """Display a preview image for a selected font.

        This function takes a font path and a font label UI element, generates a preview image
        of the font, and displays it in the UI. It also updates the selected font information.
        Args:
            font_path (str): The path to the font file.
            font_label (ui.label): The UI label element associated with the font.
        """
        global selected_font_path, selected_font_label

        if font_path:
            font_label.classes(add='bg-slate-300')
            selected_font_path = font_path
            selected_font_label = font_label
            if preview_buffer := generate_preview(font_path):
                preview_image.set_source(
                    f"data:image/png;base64,{base64.b64encode(preview_buffer.getvalue()).decode('utf-8')}"
                )

    # Populate font list initially
    search_input.value = ""  # Set an initial empty value
    filter_fonts(search_input)  # Populate the list with all fonts initially

# Run the app
ui.run()
