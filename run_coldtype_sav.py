"""
 a: zak-45
 d: 13/03/2024
 v: 1.0.0

 Coldtype class


"""

import threading
from coldtype.renderer import Renderer

class RUNColdtype:

    queue_names = {}  # queues dict

    def __init__(self):
        self.rate: int = 25
        self.stopcast: bool = True

    def t_coldtype(self, shared_list=None):
        print('inside thread')
        print(f'Rate: {self.rate}')
        print(f'SL: {shared_list}')

        _, parser = Renderer.Argparser()
        params = parser.parse_args([r"C:\Users\zak-4\PycharmProjects\WLEDVideoSync\test2.py", "-kl", "fr", "-wcs", "1", "-ec", "notepad"])

        Renderer(parser=params).main()

    def run(self, shared_list=None):
        thread = threading.Thread(target=self.t_coldtype, args=(shared_list,))
        thread.daemon = True  # Ensures the thread exits when the main program does
        thread.start()
        print('Child Coldtype initiated')




