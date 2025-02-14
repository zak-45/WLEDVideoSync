import sys
import ast

from nicegui import ui
from src.utl.niceutils import LocalFilePicker
from src.txt.coldtypemp import RUNColdtype
from src.utl.calculator import Calculator
from src.utl.console import ConsoleCapture

UPLOAD_FOLDER = './xtra/coldtype'  # Set the upload folder

class PythonEditor:
    """Run the Python code in the editor using Coldtype.

    Executes the code in the editor using the RUNColdtype class,
    providing the file path and log queue. Displays a notification
    indicating the file is running.
    """
    def __init__(self):
        """Initialize the PythonEditor.

        Sets up the initial state of the editor, including file name tracking,
        editor and preview components, syntax checker, and console capture.
        """
        self.current_file = ""  # Global variable to keep track of the loaded file name
        self.editor = None
        self.preview = None
        self.editor_file = None
        self.syntax = None
        self.py_run = None
        self.log_queue = None

        self.capture = ConsoleCapture(show_console=False)

    async def run_py(self):
        """Run the Python code in the editor using Coldtype.

        Executes the code in the editor using the RUNColdtype class,
        providing the file path and log queue. Displays a notification
        indicating the file is running.
        """
        my_python=RUNColdtype(script_file=self.editor_file.text, log_queue=self.capture.log_queue)
        my_python.start()
        ui.notify(f'File "{self.editor_file.text}" running in Coldtype. Wait ...', color='green')

    async def read_file(self, file_path):
        """Reads and displays the content of a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.preview.set_value(content)
            ui.notify(f'File "{self.current_file}" loaded.', color='green')
        except Exception as e:
            ui.notify(f'Error loading file: {e}', color='red')

    def save_file(self, editor_file):
        """Save the current content of the editor back to the specified file."""
        if editor_file:
            with open(editor_file, 'w', encoding='utf-8') as f:
                f.write(self.editor.value)
            ui.notify(f'File "{editor_file}" saved successfully!', color='green')
        else:
            ui.notify('No file to save. Please upload a file first.', color='red')

    def check_syntax(self, code):
        """Check Python syntax and return a formatted error message if any."""
        try:
            ast.parse(code)
            self.py_run.set_visibility(True)
            return "✅ No syntax errors detected."
        except SyntaxError as e:
            self.py_run.set_visibility(False)
            return f"❌ Syntax Error: {e.msg} \nLine: {e.lineno}"

    def check_code_syntax(self):
        """Check the syntax of the code in the editor and display the result."""
        code = self.editor.value
        result = self.check_syntax(code)
        self.syntax.set_text(result)
        self.syntax.set_visibility(True)

    @staticmethod
    def toggle_fullscreen():
        """Toggle fullscreen mode for the editor."""

        ui.run_javascript(''' 
            const editor = document.querySelector('.editor-container');
            const closeButton = document.querySelector('.fullscreen-close');

            if (!document.fullscreenElement) {
                editor.requestFullscreen();
                closeButton.style.display = 'block';  // Show close button
            } else {
                document.exitFullscreen();
                closeButton.style.display = 'none';  // Hide close button
            }
        ''')

    async def pick_file_to_edit(self) -> None:
        """Select a file to edit."""
        pyfile = await LocalFilePicker(f'{UPLOAD_FOLDER}', multiple=False, thumbs=False, extension='.py')
        if pyfile:
            pyfile = str(pyfile[0])
            if sys.platform.lower() == 'win32':
                pyfile = pyfile.replace('\\', '/')
            if not pyfile.startswith('./'):
                pyfile = f'./{pyfile}'
            self.current_file = pyfile
            await self.read_file(self.current_file)
            self.editor.set_value(self.preview.value),
            self.editor_file.set_text(self.current_file)
            self.syntax.set_text('')

    @staticmethod
    async def show_calculator():
        """Display a calculator dialog."""
        with ui.dialog() as dialog:
            dialog.open()
            Calculator()

    async def setup_ui(self):
        """Set up the UI layout and actions."""

        # UI Layout
        ui.label('Python Code Editor with Syntax Checking').classes('self-center text-2xl font-bold')
        with ui.row().classes('w-full max-w-4xl mx-auto mt-8 gap-0'):

            self.syntax = ui.label().classes('text-red-500 whitespace-pre-wrap')
            self.syntax.set_visibility(False)

            # Toolbar
            with ui.row().classes('w-full justify-between'):
                ui.button('Upload File', icon='folder', on_click=self.pick_file_to_edit)
                ui.button('Check Syntax',icon='check', on_click=self.check_code_syntax).classes('bg-blue-500 text-white')
                self.py_run = ui.button(icon='settings', on_click=self.run_py)
                self.py_run.set_visibility(False)
                ui.button('Fullscreen', icon='fullscreen', on_click=self.toggle_fullscreen).classes('bg-gray-700 text-white')

            ui.label('Current Editor File:').classes('text-sm text-gray-500')
            self.editor_file = ui.label(self.current_file).classes('text-sm')

            # File content preview area
            # 09/02/2025 : use it in this way to prevent NiceGUI bug :https://github.com/zauberzeug/nicegui/issues/3337
            # will use textarea to store file content and copy to editor
            self.preview = ui.textarea()
            self.preview.set_visibility(False)

            # Code editor with syntax highlighting - remove any default margins-top/padding-top
            with ui.column().classes('editor-container w-full h-96 border border-gray-300 mt-0 pt-0 gap-1'):
                with ui.row():
                    save_file = ui.button(icon='save', on_click=lambda: self.save_file(self.editor_file.text))
                    save_file.classes('bg-green-500 text-white')
                    with ui.button(icon='palette'):
                        ui.color_picker(on_pick=lambda e: ui.notify(f'You chose {e.color}'))
                    ui.button(icon='calculate', on_click=self.show_calculator)

                self.editor = ui.codemirror(language='Python', theme='dracula').classes('w-full h-full')
                self.editor.style(add='font-family:Roboto !important')

        ui.separator()

        media_exp_param = ui.expansion('Console', icon='feed', value=False)
        with media_exp_param.classes('w-full bg-sky-800 mt-2'):
            self.capture.setup_ui()


if __name__ in {"__main__", "__mp_main__"}:
    # NiceGUI app
    @ui.page('/')
    async def main_page():

        # Instantiate and run the editor
        editor_app = PythonEditor()
        await editor_app.setup_ui()

        print('Editor is running')

    ui.run(reload=False)
