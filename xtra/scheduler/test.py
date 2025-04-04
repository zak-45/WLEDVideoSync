import psutil

for process in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        print(f"PID: {process.info['pid']}, Command: {' '.join(process.info['cmdline'] or [])}")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass