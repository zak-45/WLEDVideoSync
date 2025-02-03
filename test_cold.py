import multiprocessing
from nicegui import ui
from run_coldtype import RUNColdtype


def cold_run():
    log_queue = multiprocessing.Queue()
    command_queue = multiprocessing.Queue()

    # Start Coldtype in the background
    coldtype_process = RUNColdtype(log_queue, command_queue)
    coldtype_process.start()


ui.button('click', on_click=cold_run)

ui.run()