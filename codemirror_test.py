from nicegui import events, ui

"""
with ui.dialog().props('full-width') as dialog:
    with ui.card():
        content = ui.codemirror()


def handle_upload(e: events.UploadEventArguments):
    text = e.content.read().decode('utf-8')
    content.set_value(text)
    dialog.open()

ui.upload(on_upload=handle_upload).props('accept=.py').classes('max-w-full')

ui.run()

"""
editor = ui.codemirror()

data = '123456'
upd = True

def handle_upload(e:events.UploadEventArguments ):
    global data, upd
    if upd is True:
        print(e)
        text = e.content.read().decode('utf-8')
        print(text)
        data = text
        upd = False

ui.upload(on_upload=handle_upload).props('accept=.py').classes('max-w-full')


editor.set_value(data)

def load():
    editor.set_value(data)

ui.button('load in editor', on_click=load)


ui.run()
