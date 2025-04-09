import sys
import os
import time
import site
from datetime import datetime

# === CONFIGURATION ===
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(PROJECT_ROOT, "trace_log.txt")

# === TRACE TOGGLES ===
TRACE_CALLS = True
TRACE_LINES = False  # Set to True to enable line-level trace output

# Paths to explicitly allow (edit as needed)
ALLOWED_PATHS = [
    os.path.abspath(os.path.join(PROJECT_ROOT, 'src')),
    os.path.abspath(os.path.join(PROJECT_ROOT, 'main.py')),
]

# Paths or substrings to explicitly ignore even if allowed
BLOCKED_PATHS = [
    'src/gui/schedulergui.py',
    'src/utl/noisy_module.py',
]


# Setup site-packages filter
SITE_PACKAGES_PATHS = set(site.getsitepackages())
VENVS = ('.venv', 'env', 'venv', 'Lib\\site-packages', 'site-packages')

call_times = {}

def is_external_file(filename):
    """Detect if file is from Python/lib/venv/third-party."""
    filename = os.path.abspath(filename)
    if any(venv_part in filename for venv_part in VENVS):
        return True
    if any(filename.startswith(path) for path in SITE_PACKAGES_PATHS):
        return True
    if "Python" in filename and "Lib" in filename and "site-packages" not in filename:
        return True
    return False

def is_allowed_file(filename):
    """Allow only files from specified folders or filenames."""
    filename = os.path.abspath(filename)
    return any(filename.startswith(path) for path in ALLOWED_PATHS)

def safe_repr(value):
    try:
        return repr(value)
    except Exception as e:
        return f"<unreprable: {e}>"

def trace_calls(frame, event, arg):
    code = frame.f_code
    filename = code.co_filename

    if is_external_file(filename) or not is_allowed_file(filename):
        return  # Skip non-project files

    func_name = code.co_name
    line_no = frame.f_lineno

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            current_line = lines[line_no - 1].strip()
    except Exception:
        current_line = "<could not read line>"

    local_vars = frame.f_locals.copy()
    local_vars_str = ", ".join(f"{k}={safe_repr(v)}" for k, v in local_vars.items())

    now = datetime.now().strftime('%H:%M:%S')
    short_filename = os.path.relpath(filename, PROJECT_ROOT)

    def log(msg):
        print(msg)
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except UnicodeEncodeError:
            safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(safe_msg + '\n')

    if event == 'call' and TRACE_CALLS:
        call_times[id(frame)] = time.time()
        log(f"[{now}] 📞 CALL: {func_name}() at {short_filename}:{line_no}")
        log(f"    >> {current_line}")
        if local_vars:
            log(f"    🧠 Locals: {local_vars_str}")

    elif event == 'line' and TRACE_LINES:
        log(f"[{now}] 📍 LINE: {short_filename}:{line_no} -> {current_line}")

    elif event == 'return' and TRACE_CALLS:
        duration = time.time() - call_times.pop(id(frame), time.time())
        log(f"[{now}] ✅ RETURN from {func_name}() -> {safe_repr(arg)} (after {duration:.4f}s)")

    return trace_calls

# Clear previous log and note trace status
try:
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# Trace started at {datetime.now()}\n")
        f.write(f"# TRACE_CALLS={TRACE_CALLS}, TRACE_LINES={TRACE_LINES}\n\n")
except Exception:
    pass

print(f"[TRACE] Tracing started. Calls: {TRACE_CALLS}, Lines: {TRACE_LINES}")
sys.settrace(trace_calls)
