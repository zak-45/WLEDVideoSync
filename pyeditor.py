import sys

from nicegui import ui
import ast
import os
from niceutils import LocalFilePicker

UPLOAD_FOLDER = './xtra/coldtype'  # Set the upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the upload folder exists

current_file = None  # Global variable to keep track of the loaded file name


async def read_file(file_path):
    """Reads and displays the content of a file."""
    global current_file

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        preview.set_value(content)
        ui.notify(f'File "{current_file}" loaded.', color='green')
    except Exception as e:
        ui.notify(f'Error loading file: {e}', color='red')


def save_file():
    """Save the current content of the editor back to the specified file."""
    if current_file:
        save_path = os.path.join(UPLOAD_FOLDER, current_file)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(editor.value)
        ui.notify(f'File "{current_file}" saved successfully!', color='green')
    else:
        ui.notify('No file to save. Please upload a file first.', color='red')


def check_syntax(code):
    """Check Python syntax and return a formatted error message if any."""
    try:
        ast.parse(code)
        return "✅ <strong>No syntax errors detected.</strong>"
    except SyntaxError as e:
        return f"❌ <strong>Syntax Error:</strong> {e.msg}<br><strong>Line:</strong> {e.lineno}"


def check_code_syntax():
    """Check the syntax of the code in the editor and display the result."""
    code = editor.value
    result = check_syntax(code)
    output.set_text(result)  # Use HTML formatting for better display


async def pick_file_to_edit() -> None:
    """ Select file to analyse """

    global current_file

    pyfile = await LocalFilePicker(f'{UPLOAD_FOLDER}', multiple=False, thumbs=True, extension='.py')
    if pyfile:
        pyfile = str(pyfile[0])
        if sys.platform.lower() == 'win32':
            pyfile = pyfile.replace('\\', '/')
        if not pyfile.startswith('./'):
            pyfile = f'./{pyfile}'

        current_file = pyfile
        await read_file(current_file)


with ui.row(wrap=False).classes('self-center'):

    with ui.column().classes('w-full mx-auto mt-8'):
        ui.button('select file', on_click=pick_file_to_edit).classes('mt-4')
        ui.button('Edit',on_click=lambda: editor.set_value(preview.value))
        preview = ui.textarea().classes('w-full h-64 resize-y border border-gray-300') # Match editor styling

    with ui.column().classes('w-full max-w-4xl mx-auto mt-12'):
        ui.label('Python Code Editor with Syntax Checking').classes('text-2xl font-bold mb-4')

        editor = ui.codemirror(
            language='Python',  # Python syntax highlighting
            theme='dracula',  # Dark theme
        ).classes('w-full h-64 resize-y border border-gray-300')

        # Buttons for syntax checking and saving the file
        with ui.row().classes('mt-4'):
            ui.button('Check Syntax', on_click=check_code_syntax).classes('bg-blue-500 text-white')
            ui.button('Save File', on_click=save_file).classes('bg-green-500 text-white')

        output = ui.label().classes('mt-4 text-red-500 whitespace-pre-wrap')

ui.run(reload=False)
