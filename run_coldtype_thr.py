import threading
from coldtype.renderer import Renderer

class RUNColdtype:

    def __init__(self):
        self.rate: int = 25

    def t_coldtype(self):
        print('inside thread')
        print(f'Rate: {self.rate}')

        _, parser = Renderer.Argparser()
        params = parser.parse_args(["cold_demo.py", "-wcs", "1", "-ec", "notepad"])

        Renderer(parser=params).main()

    def start(self):
        thread = threading.Thread(target=self.t_coldtype)
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        print('Thread Coldtype initiated')
