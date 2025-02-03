from nicegui import ui, app
from run_coldtype_thr import RUNColdtype

def cold_run():

    cold = RUNColdtype()
    cold.start()

ui.button('run Coldtype', on_click=cold_run)
ui.button('shutdown', on_click=app.shutdown)

print('run NiceGUI')
ui.run(reload=False)

print('end of main')
