import schedule
import time
from src.cst import desktop

Desktop = desktop.CASTDesktop()

def job():
    print("I'm casting Desktop ...")
    Desktop.stopcast = False
    Desktop.cast()

schedule.every().minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
