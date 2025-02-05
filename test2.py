from nicegui import ui, events
import os
import ast


UPLOAD_FOLDER = './xtra/coldtype'  # Set the upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the upload folder exists

current_file = None  # Global variable to keep track of the loaded file name

def handle_upload(e: events.UploadEventArguments):
    """Handle the uploaded file and load it directly into the editor."""
    global current_file
    current_file = e.name  # Store the uploaded file name
    text = e.content.read().decode('utf-8')  # Read and decode the file content
    editor.set_value(text)  # Directly set the content into the editor

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

with ui.column().classes('w-full max-w-4xl mx-auto mt-8'):
    ui.label('Python Code Editor with Syntax Checking').classes('text-2xl font-bold mb-4')

    editor = ui.codemirror(
        language='Python',  # Python syntax highlighting
        theme='dracula',  # Dark theme
    ).classes('w-full h-64 resize-y border border-gray-300')

    output = ui.label().classes('mt-4 text-red-500 whitespace-pre-wrap')

    # File upload
    upload = ui.upload(on_upload=handle_upload).classes('mt-4')
    upload.props('accept=".py"')  # Only allow .py files
    upload.props('auto-upload')  # Automatically upload the file without a button

    # Buttons for syntax checking and saving the file
    with ui.row().classes('mt-4'):
        ui.button('Check Syntax', on_click=check_code_syntax).classes('bg-blue-500 text-white')
        ui.button('Save File', on_click=save_file).classes('bg-green-500 text-white')

ui.run()
