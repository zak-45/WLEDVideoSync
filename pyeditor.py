from nicegui import ui
import ast


def check_syntax(code):
    """Check Python syntax and return error messages if any."""
    try:
        ast.parse(code)
        return "✅ No syntax errors detected."
    except SyntaxError as e:
        return f"❌ Syntax Error on line {e.lineno}: {e.msg}"


# Add Monaco Editor to the body
ui.add_body_html('''
<div id="editor-container" style="height: 300px; width: 100%; resize: both; overflow: auto; border: 1px solid #ccc;">
    <div id="editor" style="height: 100%; width: 100%;"></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.34.1/min/vs/loader.js"></script>
<script>
    require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.34.1/min/vs' }});
    require(['vs/editor/editor.main'], function() {
        window.editor = monaco.editor.create(document.getElementById('editor'), {
            value: '',
            language: 'python',
            theme: 'vs-dark'
        });
    });
</script>
''')

with ui.column().classes('w-full max-w-4xl mx-auto mt-8'):
    ui.label('Python Code Editor with Monaco').classes('text-2xl font-bold mb-4')
    preview = ui.textarea(label='File Preview').classes('w-full h-40 mt-4')
    output = ui.label().classes('mt-4 text-red-500 whitespace-pre-wrap').props('id=output')


    @ui.page('/check_syntax')
    async def syntax_endpoint(request):
        """API endpoint to check syntax and return the result."""
        data = await request.json()
        code = data.get('code', '')
        return check_syntax(code)


    def load_file(event):
        """Preview the uploaded file content before loading it into the editor."""
        content = event.content.read().decode('utf-8')
        preview.set_value(content)  # Show file content in the preview box


    ui.upload(on_upload=load_file).classes('mt-4').props('accept=".py"')


    def confirm_load():
        """Load the previewed content into the Monaco Editor."""
        ui.run_javascript(f'window.editor.setValue(`{preview.value}`);')


    ui.button('Load into Editor', on_click=confirm_load).classes('mt-2')

ui.run()
