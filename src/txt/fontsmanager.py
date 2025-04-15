import io
import base64
import os

from coldtype import StSt
from coldtype.raster import *
from nicegui import ui, app
import fontTools.ttLib

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.text')
text_logger = logger_manager.logger

class FontSetApplication:
    """
    Manages the application's font settings, including loading custom fonts and applying them to UI elements.
    This code defines a class FontSetApplication that manages custom font loading and application in a NiceGUI application.
    It loads a font file from a specified path, makes it available via the NiceGUI web server,
    and injects CSS into the application's HTML to apply the font to the body and other specific elements.

    The __init__ method takes the font path, family name, web server path, font weight, font style,
    and size adjustment as arguments.
    It determines the font type (TrueType or OpenType), adds the font directory as static files to the NiceGUI app,
    and constructs a CSS style block.
    This style block defines the @font-face rule to load the font and applies it to the body element,
    overriding the default font.
    Specific classes like console-output and nicegui-editor are excluded from the custom font.
    The get_font_type method uses the fontTools library to determine the font type from the file extension.
    """

    def __init__(self,
                 font_path,
                 font_family_name="WLEDFont",
                 path_in_webserver='/FontsPath',
                 font_weight= 'normal',
                 font_style='normal',
                 size_adjust='100%'):
        """Initialize the FontSetApplication.

        Args:
            font_path (str): The absolute path to the font file.
            font_family_name (str, optional): The name to assign to the font family. Defaults to "WLEDFont".
            path_in_webserver (str, optional): The path to serve the font from in the webserver. Defaults to '/FontsPath'.
            font_weight : normal, bold ...
            font_style : normal, italic ...
            size_adjust : percentage
        """
        self.font_path = font_path
        self.font_type = self.get_font_type(font_path)
        self.font_family_name = font_family_name
        self.path_in_webserver = path_in_webserver
        self.font_weight = font_weight
        self.font_style = font_style
        self.size_adjust = size_adjust
        self.font_dir = os.path.dirname(self.font_path)
        app.add_static_files(self.path_in_webserver, self.font_dir)

        font_url = f"{self.path_in_webserver}/{os.path.basename(self.font_path)}"
        style = f"""
        <style>
            @font-face {{
                font-family: "{self.font_family_name}";
                src: url("{font_url}") format('{self.font_type}');
                font-weight: {self.font_weight};
                font-style: {self.font_style};
                size-adjust: {self.size_adjust};
            }}

            body {{
                font-family: "{self.font_family_name}", sans-serif;
                font-size: {cfg_mgr.app_config['font_size']};
            }}
            
            .console-output {{
                font-family: "{cfg_mgr.app_config['font_family']}", sans-serif !important;
            }}
            
            .nicegui-editor {{
                font-family: "{cfg_mgr.app_config['font_family']}", sans-serif !important;
            }}
        </style>
        """
        ui.add_head_html(style)

    @staticmethod
    def get_font_type(font_path):
        """
        Detects the font type from the font file path.

        Args:
            font_path (str): Path to the font file.

        Returns:
            str: The font type (e.g., "truetype", "opentype", etc.), or "truetype" if the type cannot be determined.
        """
        try:
            font = fontTools.ttLib.TTFont(font_path)
            if 'CFF ' in font:
                return 'opentype'
            elif 'glyf' in font:
                return 'truetype'
            else:
                return 'unknown'  # Or handle other font types as needed
        except Exception as e:
            print(f"Error detecting font type: {e}")
            return "truetype"  # Default to truetype if detection fails

class FontPreviewManager:
    """Manages font preview and selection functionality.

    This class provides methods for generating font previews, filtering fonts,
    and managing font selection in a user interface.

    The FontPreviewManager class manages font previews and selection.
    It provides methods to generate font previews as PNG images, filter the available fonts based on a search query,
    and display a preview for a selected font.

    The class stores a dictionary of available fonts, the selected font path, and the associated label.
    generate_preview renders text with the given font and size using Coldtype, returning the image as a byte stream.
    filter_fonts filters the font list based on a search query.
    get_preview generates a preview image, updates the selected font information, and returns the image as a base64
    encoded string for display in a UI.

    """

    def __init__(self, fonts):
        """Initialize the FontPreviewManager with available fonts.

        Args:
            fonts (dict): A dictionary of available fonts with font names as keys and paths as values.
        """
        self.font_size = 25
        self.fonts = fonts
        self.selected_font_path = None
        self.selected_font_label = ui.label()

    def generate_preview(self, font_path, preview_text="The quick brown fox jumps over the lazy dog"):
        """Generate a PNG preview image of a font.

        This method renders a given text string using the specified font and returns a byte stream
        containing the PNG image. If the preview cannot be generated, it returns None.

        Args:
            font_path (str): The path to the font file.
            preview_text (str, optional): The text string to render. Defaults to standard pangram.

        Returns:
            io.BytesIO | None: A byte stream containing the PNG image, or None if preview generation fails.
        """
        try:
            font_rectangle = Rect(800, 100)
            font_image = (StSt(text=preview_text, font=font_path, font_size=self.font_size)
                          .align(font_rectangle)
                          .chain(rasterized(font_rectangle, wrapped=False)))

            img_buffer = io.BytesIO()
            font_image.save(img_buffer, skia.kPNG)
            img_buffer.seek(0)
            return img_buffer

        except Exception as e:
            print(f"Could not generate preview: {e}")
            return None

    def filter_fonts(self, query):
        """Filter available fonts based on a search query.

        This method filters the font list based on a case-insensitive search query
        and returns matching font names.

        Args:
            query (str): The search query to filter fonts.

        Returns:
            list: A list of font names matching the query.
        """
        return [
            font_name for font_name in sorted(self.fonts.keys())
            if query.lower() in font_name.lower()
        ]

    def get_preview(self, font_path, font_label):
        """Display a preview image for a selected font.

        This method generates and sets a preview image for the selected font.

        Args:
            font_path (str): The absolute path to the font file.
            font_label (ui.label): The UI label element associated with the font.

        Returns:
            str | None: Base64 encoded preview image or None if preview generation fails.
        """
        if font_path:
            self.selected_font_path = font_path
            self.selected_font_label = font_label

            if preview_buffer := self.generate_preview(font_path):
                return f"data:image/png;base64,{base64.b64encode(preview_buffer.getvalue()).decode('utf-8')}"
        return None
