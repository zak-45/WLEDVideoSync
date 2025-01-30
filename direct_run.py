"""
run Coldtype programmatically
"""

from threading import Thread
from coldtype.renderer import Renderer

_, parser = Renderer.Argparser()
params = parser.parse_args(["test1.py","-kl","fr","-wcs","1"])

def run():
    print('start coldtype')
    # run Coldtype with params
    Renderer(parser=params).main()

thread = Thread(target=lambda: run())
thread.daemon = True  # Ensures the thread exits when the main program does
thread.start()
thread.join()

print('end of coldtype')
