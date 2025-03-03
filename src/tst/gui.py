import multiprocessing
import sys
from nicegui import ui
from subprocess import Popen


def mp_setup():
    if sys.platform.lower() != 'linux':
        return multiprocessing.Process, multiprocessing.Queue  # Direct return
    ctx = multiprocessing.get_context('spawn')
    return ctx.Process, ctx.Queue

Process, Queue = mp_setup()

def mycmd():
    print('into my cmd')

    proc = Popen([sys.executable, "-m", "CastAPI"])

def proc():
    new_process = Process(target=mycmd)
    # start the child process
    new_process.start()
    print(f'new process started {new_process}')


if __name__ in "__main__":
    print('start')
    ui.button('start new process', on_click=proc)
    ui.run(reload=False)
    print('end')