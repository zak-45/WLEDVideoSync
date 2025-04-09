import sys
import os
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # limit tracing to your project
LOG_FILE = os.path.join(PROJECT_ROOT, "trace_log.txt")

# Store timing for return duration reporting
call_times = {}

def trace_calls(frame, event, arg):
    code = frame.f_code
    filename = code.co_filename

    if not filename.startswith(PROJECT_ROOT):
        return  # Skip external files

    func_name = code.co_name
    line_no = frame.f_lineno

    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
            current_line = lines[line_no - 1].strip()
    except Exception:
        current_line = "<could not read line>"

    local_vars = frame.f_locals.copy()
    local_vars_str = ", ".join(f"{k}={v!r}" for k, v in local_vars.items())

    now = datetime.now().strftime('%H:%M:%S')
    short_filename = os.path.relpath(filename, PROJECT_ROOT)

    # Logging utility
    def log(msg):
        print(msg)
        with open(LOG_FILE, 'a') as f:
            f.write(msg + '\n')

    if event == 'call':
        call_times[id(frame)] = time.time()
        log(f"[{now}] 📞 CALL: {func_name}() at {short_filename}:{line_no}")
        log(f"    >> {current_line}")
        if local_vars:
            log(f"    🧠 Locals: {local_vars_str}")
    elif event == 'line':
        log(f"[{now}] 📍 LINE: {short_filename}:{line_no} -> {current_line}")
    elif event == 'return':
        duration = time.time() - call_times.pop(id(frame), time.time())
        log(f"[{now}] ✅ RETURN from {func_name}() -> {arg!r} (after {duration:.4f}s)")

    return trace_calls

# Clear previous log
try:
    with open(LOG_FILE, 'w') as f:
        f.write(f"# Trace started at {datetime.now()}\n\n")
except Exception:
    pass

sys.settrace(trace_calls)
