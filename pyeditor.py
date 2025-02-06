import sys
import ast
from nicegui import ui
from niceutils import LocalFilePicker

UPLOAD_FOLDER = './xtra/coldtype'  # Set the upload folder
current_file = ""  # Global variable to keep track of the loaded file name


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


def save_file(editor_file):
    """Save the current content of the editor back to the specified file."""
    if editor_file:
        with open(editor_file, 'w', encoding='utf-8') as f:
            f.write(editor.value)
        ui.notify(f'File "{editor_file}" saved successfully!', color='green')
    else:
        ui.notify('No file to save. Please upload a file first.', color='red')


def check_syntax(code):
    """Check Python syntax and return a formatted error message if any."""
    try:
        ast.parse(code)
        return "✅ No syntax errors detected."
    except SyntaxError as e:
        return f"❌ Syntax Error: {e.msg} \nLine: {e.lineno}"


def check_code_syntax():
    """Check the syntax of the code in the editor and display the result."""
    code = editor.value
    result = check_syntax(code)
    output.set_text(result)  # Use HTML formatting for better display


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


async def pick_file_to_edit() -> None:
    """Select a file to edit."""
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


# UI Layout
with ui.row().classes('w-full max-w-4xl mx-auto mt-8'):
    # Toolbar
    with ui.row().classes('w-full justify-between mb-4'):
        ui.button('Upload File', icon='folder', on_click=pick_file_to_edit)
        ui.button('Edit File', icon='edit', on_click=lambda: (
            editor.set_value(preview.value),
            editor_file.set_text(current_file)
        ))
        ui.button('Save Editor File', icon='save', on_click=lambda: save_file(editor_file.text)).classes(
            'bg-green-500 text-white')
        ui.button('Fullscreen Editor', icon='fullscreen', on_click=toggle_fullscreen).classes('bg-gray-700 text-white')

    # Labels to show the current file paths
    ui.label('Current Uploaded File:').classes('text-sm text-gray-500')
    file = ui.label(current_file).classes('text-sm')
    file.bind_text_from(locals(), "current_file")

    ui.label('Current Editor File:').classes('text-sm text-gray-500')
    editor_file = ui.label(current_file).classes('text-sm')

    # File content preview area
    preview = ui.textarea().classes('w-full h-84 resize-y border border-gray-300')
    preview.props(add='placeholder="File Preview" rows="2"')

    # Code editor with syntax highlighting
    ui.label('Python Code Editor with Syntax Checking').classes('text-2xl font-bold mt-8')
    # editor = ui.codemirror(language='Python', theme='dracula').classes('w-full h-96 resize-y border border-gray-300')

    with ui.column().classes('editor-container w-full h-96 border border-gray-300'):
        editor = ui.codemirror(language='Python', theme='dracula').classes('w-full h-full')


    # Syntax check output and button
    with ui.row().classes('mt-4'):
        ui.button('Check Syntax', on_click=check_code_syntax).classes('bg-blue-500 text-white')
        output = ui.label().classes('mt-4 text-red-500 whitespace-pre-wrap')

ui.run(reload=False)
