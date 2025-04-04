import schedule
import time
from src.cst import media
from configmanager import ConfigManager

cfg_mgr = ConfigManager()
Media=media.CASTMedia()

def job():
    print("I'm casting something to WLED...")
    Media.stopcast = False
    Media.host = '192.168.1.125'
    Media.wled = True
    Media.preview = False
    Media.viinput = cfg_mgr.app_root_path("xtra/bg-anim03.gif")
    Media.cast()

schedule.every(10).seconds.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
