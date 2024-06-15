# run chart on its own process
import subprocess
import sys

dark_mode = False


def select_exe():
    if sys.platform == 'linux':
        return './runcharts.bin'

    elif sys.platform == 'darwin':
        return './runcharts.app'

    else:
        return './runcharts.exe'


subprocess.Popen(["devstats", str(dark_mode)],
                 executable=select_exe(),
                 stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE,
                 text=True)


subprocess.Popen(["netstats", str(dark_mode)],
                 executable=select_exe(),
                 stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE,
                 text=True)


subprocess.Popen(["sysstats", str(dark_mode)],
                 executable=select_exe(),
                 stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE,
                 text=True)
