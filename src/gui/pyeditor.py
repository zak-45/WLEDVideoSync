"""
a: zak-45
d: 01/02/2025
v: 1.0.0.0

Python Editor
use the built-in python
This editor is mainly for advanced text animation effect.
You can use module Coldetype, class TextAnimator, module moviepy ...
CV2 provide a way to have a preview window.
Desktop queues could be used to send frames (numpy array) to any net devices (art-net/e131/DDP)

"""
import ast
import os
import traceback

from nicegui import ui
from src.gui.niceutils import LocalFilePicker
from src.txt.coldtypemp import RUNColdtype
from src.gui.calculator import Calculator
from src.utl.console import ConsoleCapture
from src.utl.utils import CASTUtils as Utils
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger')


class PythonEditor:
    """Run the Python code in the editor using Coldtype.

    Executes the code in the editor using the RUNColdtype class,
    providing the file path and log queue. Displays a notification
    indicating the file is running.
    """
    def __init__(self,
                 upload_folder=cfg_mgr.app_root_path('xtra/text'),
                 file_to_load: str = None,
                 use_capture:bool = True,
                 go_back: bool = True,
                 coldtype: bool = True):
        """Initialize the PythonEditor.

        Sets up the initial state of the editor, including file name tracking,
        editor and preview components, syntax checker, and console capture.
        """

        # File content preview area
        # 09/02/2025 : use it in this way to prevent NiceGUI bug :https://github.com/zauberzeug/nicegui/issues/3337
        # will use textarea to store file content and copy to editor
        self.preview = ui.textarea()
        self.preview.set_visibility(False)

        self.coldtype = coldtype
        self.current_file = ""  # Global variable to keep track of the loaded file name
        if file_to_load:
            self.current_file = file_to_load
            self.read_file(file_to_load)
        self.editor = None
        self.editor_file = None
        self.syntax = None
        self.py_run = None
        self.log_queue = None
        self.upload_folder = upload_folder
        self.use_capture = use_capture
        if self.use_capture:
            self.capture = ConsoleCapture(show_console=False)
        self.go_back = go_back

    @staticmethod
    async def get_manager_queues():
        """Retrieve information about Desktop queues from the queue manager.

        Connects to the queue manager and retrieves information about
        available shared Lists . Returns an empty dictionary if the
        connection fails.
        """
        client = Utils.attach_to_queue_manager()
        return client.get_shared_lists_info() if client.connect() else {}


    @staticmethod
    async def show_queues():
        """Display shared queues information in a dialog.

        Retrieves queue information and presents it in a read-only
        JSON editor within a dialog box.
        """
        queues = await PythonEditor.get_manager_queues()
        print(queues)
        with ui.dialog() as dialog, ui.card():
            dialog.open()
            await ui.json_editor({'content': {'json': queues}}) \
                .run_editor_method('updateProps', {'readOnly': True})
            ui.button('Close', on_click=dialog.close, color='red')
            
    async def run_py(self):
        """Run the Python code in the editor using Coldtype or built-in Python.

        Executes the code in the editor using the RUNColdtype class,
        providing the file path and log queue. Displays a notification
        indicating the file is running.
        """
        if self.coldtype:
            src_python=RUNColdtype(script_file=self.editor_file.text, log_queue=self.capture.log_queue if self.use_capture else None)
            src_python.start()
            cfg_mgr.logger.debug(f'File "{self.editor_file.text}" running in Coldtype.')
            ui.notify(f'File "{self.editor_file.text}" running in Coldtype. Wait ...', color='green')
        else:
            try:
                code = self.editor.value
                """
                # Redirect stdout and stderr to the capture if enabled
                if self.use_capture:
                    original_stdout = sys.stdout
                    original_stderr = sys.stderr
                    sys.stdout = self.capture.log_queue
                    sys.stderr = self.capture.log_queue
                """

                # Execute the code
                exec(code)

                """
                if self.use_capture:
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                """

                cfg_mgr.logger.debug(f'Code executed successfully.')
                ui.notify(f'Code executed successfully.', color='green')
            except Exception as e:
                """
                if self.use_capture:
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                """
                cfg_mgr.logger.error(f'Error executing code: {e}')
                ui.notify(f'Error executing code: {e}', color='red')
                if self.use_capture:
                    self.capture.log_queue.write(traceback.format_exc())

    def read_file(self, file_path):
        """Reads and displays the content of a file."""

        print(f'locals : {locals()}')
        print(f'globals: {globals()}')
        print(f'dir    : {dir()}')
        print(f'env    : {os.environ}')
        print(f'pwd    : {os.getcwd()}')

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.preview.set_value(content)
            cfg_mgr.logger.debug(f'Pyeditor File "{self.current_file}" loaded.')
            ui.notify(f'File "{self.current_file}" loaded.', color='green')
        except Exception as e:
            cfg_mgr.logger.error(f'Pyeditor Error to load File "{self.current_file}".')
            ui.notify(f'Error loading file: {e}', color='red')

    async def save_file(self, editor_file):
        """Save the current content of the editor back to the specified file."""
        if editor_file:
            try:
                with open(editor_file, 'w', encoding='utf-8') as f:
                    f.write(self.editor.value)
                cfg_mgr.logger.debug(f'File "{editor_file}" saved successfully!')
                ui.notify(f'File "{editor_file}" saved successfully!', color='green')
            except Exception as e:
                cfg_mgr.logger.error(f'File "{editor_file}" not saved: {e} ')
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
        ''', timeout=2)

    async def pick_file_to_edit(self) -> None:
        """Select a file to edit."""
        if os.path.isdir(self.upload_folder):
            pyfile = await LocalFilePicker(f'{self.upload_folder}',multiple=False, thumbs=False)
            if pyfile:
                pyfile = str(pyfile[0])
                self.current_file = pyfile
                self.read_file(self.current_file)
                self.editor.set_value(self.preview.value),
                self.editor_file.set_text(self.current_file)
                self.syntax.set_text('')
        else:
            cfg_mgr.logger.warning(f'Folder do not exist: {self.upload_folder}')


    def get_text(self):
        return self.editor_file.text


    @staticmethod
    async def show_calculator():
        """Display a calculator dialog."""
        with ui.dialog() as dialog:
            dialog.open()
            Calculator()


    def do_go_back(self):
        """Go back to the previous page."""
        if self.use_capture:
            self.capture.restore()
        if self.go_back:
            ui.navigate.back()

    async def setup_ui(self):
        """Set up the UI layout and actions."""

        # UI Layout
        ui.label('Python Code Editor with Syntax Checking').classes('self-center text-2xl font-bold')
        run_type = 'Coldtype' if self.coldtype else 'Python'
        ui.label(f'Run Type: {run_type}').classes('self-center text-sm')
        if self.go_back:
            ui.button(icon='reply', on_click=self.do_go_back)
        with ui.row().classes('w-full max-w-4xl mx-auto mt-8 gap-0'):

            # Toolbar
            with ui.row().classes('w-full justify-between'):
                if run_type == 'Coldtype':
                    ui.button('Upload File', icon='folder', on_click=self.pick_file_to_edit)
                ui.button('Check Syntax',icon='check', on_click=self.check_code_syntax).classes('bg-blue-500 text-white')
                ui.button('Fullscreen', icon='fullscreen', on_click=self.toggle_fullscreen).classes('bg-gray-700 text-white')

            ui.label('Current Editor File:').classes('text-sm text-gray-500')
            self.editor_file = ui.label(self.current_file).classes('text-sm')
            self.syntax = ui.label().classes('text-red-500 whitespace-pre-wrap')
            self.syntax.set_visibility(False)

            # Code editor with syntax highlighting - remove any default margins-top/padding-top
            with ui.column().classes('editor-container w-full h-96 border border-gray-300 mt-0 pt-0 gap-1'):
                with ui.row():
                    if run_type == 'Coldtype' or self.current_file != '':
                        save_file = ui.button(icon='save', on_click=lambda: self.save_file(self.editor_file.text))
                        save_file.classes('bg-green-500 text-white')
                    self.py_run = ui.button(icon='settings', on_click=self.run_py)
                    self.py_run.set_visibility(False)
                    with ui.button(icon='palette'):
                        ui.color_picker(on_pick=lambda e: ui.notify(f'You chose {e.color}'))
                    ui.button(icon='calculate', on_click=self.show_calculator)
                    ui.button(icon='queue', on_click=PythonEditor.show_queues)

                self.editor = ui.codemirror(language='Python', theme='dracula').classes('w-full h-full')
                self.editor.style(add='font-family:Roboto !important')
                self.editor.set_value(self.preview.value)

        ui.separator()

        if self.use_capture:
            media_exp_param = ui.expansion('Console', icon='feed', value=False)
            with media_exp_param.classes('w-full bg-sky-800 mt-2'):
                self.capture.setup_ui()


if __name__ == "__main__":
    from nicegui import app

    py_file = cfg_mgr.app_root_path('xtra/scheduler/WLEDScheduler.py')

    # NiceGUI app
    @ui.page('/')
    async def main_page_editor():
        # Instantiate and run the editor
        editor_python = PythonEditor(use_capture=False,go_back=False, coldtype=False)
        await editor_python.setup_ui()
        editor_file_python = PythonEditor(file_to_load=py_file,use_capture=False,go_back=False, coldtype=False)
        await editor_file_python.setup_ui()
        editor_coldtype = PythonEditor(use_capture=True, upload_folder=cfg_mgr.app_root_path('xtra/text'), go_back=False)
        await editor_coldtype.setup_ui()
        ui.button('shutdown', on_click=app.shutdown).classes('self-center')
        print('Editor is running')

    ui.run(reload=False)
