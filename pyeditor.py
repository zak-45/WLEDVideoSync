import multiprocessing
import sys
import ast

from nicegui import ui
from niceutils import LocalFilePicker
from coldtypemp import RUNColdtype
from calculator import Calculator
from console import ConsoleCapture

UPLOAD_FOLDER = './xtra/coldtype'  # Set the upload folder

class PythonEditor:
    def __init__(self):
        self.current_file = ""  # Global variable to keep track of the loaded file name
        self.editor = None
        self.preview = None
        self.editor_file = None
        self.syntax = None
        self.py_run = None
        self.log_queue = None

        self.capture = ConsoleCapture(show_console=False)

    async def run_py(self):
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


    def toggle_fullscreen(self):
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

    async def pick_file_to_edit(self, label) -> None:
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
        with ui.dialog() as dialog:
            dialog.open()
            Calculator()

    def setup_ui(self):
        """Setup the UI layout and actions."""

        # UI Layout
        ui.label('Python Code Editor with Syntax Checking').classes('self-center text-2xl font-bold')
        with ui.row().classes('w-full max-w-4xl mx-auto mt-8'):
            # Toolbar
            with ui.row().classes('w-full justify-between mb-4'):
                ui.button('Upload File', icon='folder', on_click=self.pick_file_to_edit)
                """
                ui.button('Edit File', icon='edit', on_click=lambda: (
                    self.editor.set_value(self.preview.value),
                    self.editor_file.set_text(self.current_file)
                ))
                """
                ui.button('Check Syntax', on_click=self.check_code_syntax).classes('bg-blue-500 text-white')
                ui.button('Save File', icon='save', on_click=lambda: self.save_file(self.editor_file.text)).classes(
                    'bg-green-500 text-white')
                ui.button('Fullscreen', icon='fullscreen', on_click=self.toggle_fullscreen).classes('bg-gray-700 text-white')

            """
            # Labels to show the current file paths
            ui.label('Current Uploaded File:').classes('text-sm text-gray-500')
            file = ui.label(self.current_file).classes('text-sm')
            file.bind_text_from(self,'current_file')
            """

            ui.label('Current Editor File:').classes('text-sm text-gray-500')
            self.editor_file = ui.label(self.current_file).classes('text-sm')
            self.syntax = ui.label().classes('text-red-500 whitespace-pre-wrap')
            self.syntax.set_visibility(False)
            self.py_run = ui.button(icon='settings', on_click=self.run_py)
            self.py_run.set_visibility(False)

            # File content preview area
            self.preview = ui.textarea().classes('w-full h-84 resize-y border border-gray-300')
            self.preview.props(add='placeholder="F i l e   P r e v i e w" rows="2"')
            self.preview.set_visibility(False)

            # Code editor with syntax highlighting
            with ui.column().classes('editor-container w-full h-96 border border-gray-300'):
                self.editor = ui.codemirror(language='Python', theme='dracula').classes('w-full h-full')
                self.editor.style(add='font-family:Roboto !important')

                with ui.row():
                    with ui.button(icon='palette'):
                        picker = ui.color_picker(on_pick=lambda e: ui.notify(f'You chose {e.color}'))
                    ui.button(icon='calculate', on_click=self.show_calculator)

        self.capture.setup_ui()


if __name__ in {"__main__", "__mp_main__"}:
    # NiceGUI app
    @ui.page('/')
    def main_page():

        # Instantiate and run the editor
        editor_app = PythonEditor()
        editor_app.setup_ui()

        print('Editor is running')

    ui.run(reload=False)
