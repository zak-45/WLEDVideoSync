import sys
import os
import time
import site
import platform
from datetime import datetime
import configparser

# === CONFIGURATION ===
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(PROJECT_ROOT, "trace_log.txt")
HTML_LOG_FILE = os.path.join(PROJECT_ROOT, "trace_log.html")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "tracetool.ini")

DEFAULT_CONFIG = {
    'trace': {
        'trace_calls': 'true',
        'trace_lines': 'false',
    },
    'filter': {
        'allowed_paths': 'src, main.py',
        'blocked_modules': 'src.gui.schedulergui, src.utl.experimental',
        'blocked_paths': 'src/gui/schedulergui.py, src/utl/noisy_module.py',
    }
}

config = configparser.ConfigParser()

def write_default_config(path):
    for section, values in DEFAULT_CONFIG.items():
        config[section] = values
    with open(path, 'w') as f:
        config.write(f)
    print(f"[TRACE] Default config written to {path}")

if not os.path.exists(CONFIG_PATH):
    write_default_config(CONFIG_PATH)
else:
    config.read(CONFIG_PATH)

def get_bool(section, key, default=False):
    return config.get(section, key, fallback=str(default)).lower() in ('1', 'true', 'yes')

def get_list(section, key, default=None):
    raw = config.get(section, key, fallback='')
    return [item.strip() for item in raw.split(',') if item.strip()] if raw else (default or [])

TRACE_CALLS = get_bool('trace', 'trace_calls', True)
TRACE_LINES = get_bool('trace', 'trace_lines', False)
BLOCKED_MODULES = get_list('filter', 'blocked_modules')
BLOCKED_PATHS = get_list('filter', 'blocked_paths')
ALLOWED_PATHS_CONFIG = get_list('filter', 'allowed_paths')

ALLOWED_PATHS = [
    os.path.abspath(os.path.join(PROJECT_ROOT, path))
    for path in ALLOWED_PATHS_CONFIG
]

SITE_PACKAGES_PATHS = set(site.getsitepackages())
VENVS = ('.venv', 'env', 'venv', 'Lib\\site-packages', 'site-packages')

call_times = {}

def is_external_file(filename):
    if not filename or not os.path.isabs(filename):
        return True
    filename = os.path.abspath(filename)
    if any(venv_part in filename for venv_part in VENVS):
        return True
    if any(filename.startswith(path) for path in SITE_PACKAGES_PATHS):
        return True
    if "Python" in filename and "Lib" in filename and "site-packages" not in filename:
        return True
    return False

def is_allowed_file(filename):
    filename = os.path.abspath(filename)
    return any(filename.startswith(path) for path in ALLOWED_PATHS)

def safe_repr(value):
    try:
        return repr(value)
    except Exception as e:
        return f"<unreprable: {e}>"

def html_log_init():
    def html_list(title, items, ident):
        if not items:
            return f'<div class="section"><h3 onclick="toggle(\'{ident}\')">▶ {title}</h3><div id="{ident}" class="collapsible-content"><p><i>None</i></p></div></div>'
        return (
            f'<div class="section"><h3 onclick="toggle(\'{ident}\')">▶ {title}</h3>'
            f'<div id="{ident}" class="collapsible-content"><ul>' +
            ''.join(f'<li>{item}</li>' for item in items) +
            '</ul></div></div>'
        )

    if not os.path.exists(HTML_LOG_FILE):
        with open(HTML_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Trace Log</title>
    <style>
        body {{ font-family: monospace; background: #111; color: #eee; padding: 1em; }}
        .call {{ color: #8be9fd; }}
        .line {{ color: #50fa7b; }}
        .return {{ color: #ffb86c; }}
        .locals {{ color: #bd93f9; }}
        h1, h3 {{ color: #f1fa8c; cursor: pointer; }}
        ul {{ margin: 0 0 1em 1em; }}
        .section {{ margin-bottom: 1em; }}
        .collapsible-content {{ display: none; padding-left: 1em; }}
    </style>
    <script>
    function toggle(id) {{
        const el = document.getElementById(id);
        if (el.style.display === "none") {{
            el.style.display = "block";
        }} else {{
            el.style.display = "none";
        }}
    }}
    function toggleAll(show) {{
        const sections = document.getElementsByClassName("collapsible-content");
        for (let i = 0; i < sections.length; i++) {{
            sections[i].style.display = show ? "block" : "none";
        }}
    }}
    </script>
</head>
<body>
<div style="margin-bottom: 1em;">
    <button onclick="toggleAll(true)">📂 Expand All</button>
    <button onclick="toggleAll(false)">📁 Collapse All</button>
</div>

<h1>Trace Log</h1>

<div class="section">
    <h3 onclick="toggle('sysinfo')">▶ System Info</h3>
    <div id="sysinfo" class="collapsible-content">
        <ul>
            <li><b>Python Version:</b> {platform.python_version()}</li>
            <li><b>Platform:</b> {platform.system()} {platform.release()}</li>
            <li><b>Architecture:</b> {platform.machine()}</li>
            <li><b>Executable:</b> {sys.executable}</li>
            <li><b>Working Dir:</b> {os.getcwd()}</li>
            <li><b>Started From:</b> {sys.argv[0]}</li>
        </ul>
    </div>
</div>

<div class="section">
    <h3 onclick="toggle('settings')">▶ Trace Settings</h3>
    <div id="settings" class="collapsible-content">
        <ul>
            <li><b>TRACE_CALLS:</b> {TRACE_CALLS}</li>
            <li><b>TRACE_LINES:</b> {TRACE_LINES}</li>
            <li><b>Log File:</b> {LOG_FILE}</li>
        </ul>
    </div>
</div>

{html_list("Allowed Paths", ALLOWED_PATHS, "allowed")}
{html_list("Blocked Paths", BLOCKED_PATHS, "blocked_paths")}
{html_list("Blocked Modules", BLOCKED_MODULES, "blocked_modules")}

<hr>
<pre>
""")

def log(msg, style_class=None):
    print(msg)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except UnicodeEncodeError:
        safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(safe_msg + '\n')

    html_line = msg.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    css_class = f' class="{style_class}"' if style_class else ''
    with open(HTML_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'<span{css_class}>{html_line}</span><br>\n')

def trace_calls(frame, event, arg):
    code = frame.f_code
    filename = code.co_filename
    module_name = frame.f_globals.get('__name__', '')

    if not filename or is_external_file(filename) or not is_allowed_file(filename):
        return

    rel_path = os.path.relpath(filename, PROJECT_ROOT).replace('\\', '/')
    if any(block in rel_path for block in BLOCKED_PATHS):
        return
    if any(module_name.startswith(block) for block in BLOCKED_MODULES):
        return

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

    if event == 'call' and TRACE_CALLS:
        call_times[id(frame)] = time.time()
        log(f"[{now}] 📞 CALL: {func_name}() at {rel_path}:{line_no}", "call")
        log(f"    >> {current_line}", "line")
        if local_vars:
            log(f"    🧠 Locals: {local_vars_str}", "locals")
    elif event == 'line' and TRACE_LINES:
        log(f"[{now}] 📍 LINE: {rel_path}:{line_no} -> {current_line}", "line")
    elif event == 'return' and TRACE_CALLS:
        duration = time.time() - call_times.pop(id(frame), time.time())
        log(f"[{now}] ✅ RETURN from {func_name}() -> {safe_repr(arg)} (after {duration:.4f}s)", "return")

    return trace_calls

# === INIT ===
try:
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# Trace started at {datetime.now()}\n\n")
except Exception:
    pass

html_log_init()
sys.settrace(trace_calls)
