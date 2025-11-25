"""
a: zak-45
d: 14/04/2025
v: 1.0.0.0

Tracetool

At its core, tracetool.py is a custom Python script designed to trace the execution of another Python program.

It hooks into the standard sys.settrace mechanism to monitor function calls, line executions, and function returns
within your project, while attempting to filter out noise from external libraries or unwanted modules/paths.

It logs this trace information to both a plain text file (trace_log.txt) and a more interactive HTML file(trace_log.html).

Key Features & Workflow

1.Configuration (tracetool.ini):
    •The script first looks for a tracetool.ini file in the same directory.
    •If the file doesn't exist, it creates one with default settings (defined in DEFAULT_CONFIG).
    These defaults enable call tracing but disable line-by-line tracing and set up some basic filtering examples.

    •It reads settings like whether to trace function calls (trace_calls), individual lines (trace_lines),
    or local variables (trace_vars).

    •It also reads filtering rules:

    •allowed_paths: Only files within these relative paths (e.g., src) will be traced.
    •blocked_modules: Functions within these modules (e.g., src.gui.schedulergui) will be ignored.
    •blocked_paths: Specific file paths to ignore.
    •function_name_contains, file_name_contains: Optional filters to only trace functions/files whose names include
    specific substrings.

2.Filtering Logic:•Before tracing anything within a function call or line event, the script performs several checks:
    •is_external_file: Tries to determine if a file belongs to the standard library,
    a virtual environment (.venv, Lib/site-packages), or installed site packages. These are generally skipped.
    •is_allowed_file: Checks if the file's absolute path starts with one of the configured ALLOWED_PATHS.
    •It then checks against the BLOCKED_MODULES, BLOCKED_PATHS, FUNC_FILTERS, and FILE_FILTERS from the config file.
    •Only if a frame passes all these checks will it be traced and logged.

3.Tracing Mechanism (sys.settrace):
    •The script defines a function trace_calls(frame, event, arg).
    •sys.settrace(trace_calls) tells the Python interpreter to call this function whenever certain events occur during execution.
    •The event argument tells the function what happened:
    •'call': A function is being called.
    •'line': The interpreter is about to execute a line of code.
    •'return': A function is about to return.
    •(Other events like 'exception' exist but aren't explicitly handled here).

4.Event Handling (trace_calls function):
    •On 'call':
    •If TRACE_CALLS is enabled and the frame passes filters:
    •It records the start time (call_times).
    •It stores the initial local variables (last_locals).
    •It logs the function name, file path, line number, and optionally the initial local variables to both log files.
    •Crucially, it returns trace_calls itself. This tells sys.settrace to keep tracing events within this function
    call (like 'line' and 'return'). If it returned None, tracing would stop for the scope of that function.
    •On 'line':
    •If TRACE_LINES is enabled and the frame passes filters:
    •It logs the file, line number, and the source code of that line.
    •If TRACE_VARS is enabled, it compares current local variables to the previously stored ones (last_locals) and
    logs any changes.
    •On 'return':
    •If TRACE_CALLS is enabled and the frame passes filters:
    •It calculates the execution duration using the stored start time.
    •It logs the return value and the duration.
    •It cleans up the stored start time and local variables for that frame.

5.Logging (log function):
    •Takes a message and writes it to trace_log.txt.
    •Formats the message as HTML (escaping special characters, optionally wrapping in a styled <span> or using
    raw HTML for <details> tags) and appends it to trace_log.html.
    •Includes basic error handling for UnicodeEncodeError.

6.HTML Output (html_log_init, log):
    •html_log_init creates the trace_log.html file if it doesn't exist, writing the basic HTML structure, CSS styles,
    and JavaScript for interactivity.
    •The HTML includes:
    •Buttons to expand/collapse all sections or just the call details.
    •Collapsible sections for System Info, Trace Settings, and the filter lists (Allowed/Blocked Paths/Modules).
    •CSS to style the different log message types (call, line, return, locals).
    •The log function uses <details> and <summary> tags for function calls, making the call blocks collapsible
    in the HTML output.

How to Use It

    You would typically import this script at the very beginning of your main application script (main.py or similar).
    Just importing it (import tracetool) is enough to activate the tracing,
    as sys.settrace(trace_calls) is called at the bottom of tracetool.py.
    Your application then runs as usual,
    and tracetool intercepts and logs the execution flow according to its configuration.

"""

import sys
import os
import time
import site
import platform
from datetime import datetime
import configparser
import numpy as np
import threading

# === CONFIGURATION ===
from configmanager import cfg_mgr

LOG_FILE = cfg_mgr.app_root_path("log/trace_log.txt")
HTML_LOG_FILE = cfg_mgr.app_root_path("log/trace_log.html")
CONFIG_PATH = cfg_mgr.app_root_path("config/tracetool.ini")

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
    """Writes the default configuration to the specified path.

    This function iterates through the DEFAULT_CONFIG dictionary and writes each
    section and its key-value pairs to a configuration file at the given path.
    It then prints a confirmation message indicating the file's location.

    Args:
        path (str): The path to write the default configuration file.
    """
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
    """Retrieves a boolean value from the configuration.

    This function attempts to read a value from the specified section and key
    in the configuration. It handles various truthy/falsy string representations
    (1, true, yes) and returns a boolean. If the key is not found, it returns
    the provided default value.

    Args:
        section (str): The configuration section.
        key (str): The configuration key.
        default (bool, optional): The default value if the key is not found.
            Defaults to False.

    Returns:
        bool: The boolean value from the configuration or the default.
    """
    return config.get(section, key, fallback=str(default)).lower() in ('1', 'true', 'yes')


def get_list(section, key, default=None):
    """Retrieves a list of strings from the configuration.

    This function reads a comma-separated string from the specified section and key
    in the configuration, splits it into a list of strings, and strips whitespace
    from each item. If the key is not found or the value is empty, it returns
    the provided default value or an empty list.

    Args:
        section (str): The configuration section.
        key (str): The configuration key.
        default (list, optional): The default value if the key is not found or the value is empty.
            Defaults to None.

    Returns:
        list: A list of strings from the configuration or the default.
    """
    raw = config.get(section, key, fallback='')
    return [item.strip() for item in raw.split(',') if item.strip()] if raw else (default or [])


TRACE_CALLS = get_bool('trace', 'trace_calls', True)
TRACE_LINES = get_bool('trace', 'trace_lines', False)
TRACE_VARS = get_bool('trace', 'trace_vars', True)
BLOCKED_MODULES = get_list('filter', 'blocked_modules')
BLOCKED_PATHS = get_list('filter', 'blocked_paths')
FUNC_FILTERS = get_list('filter', 'function_name_contains')
FILE_FILTERS = get_list('filter', 'file_name_contains')
ALLOWED_PATHS_CONFIG = get_list('filter', 'allowed_paths')

ALLOWED_PATHS = [
    os.path.abspath(cfg_mgr.app_root_path(path))
    for path in ALLOWED_PATHS_CONFIG
]

SITE_PACKAGES_PATHS = set(site.getsitepackages())
VENVS = ('.venv', 'env', 'venv', 'Lib\\site-packages', 'site-packages')

call_times = {}
last_locals = {}
# Track current active frames to isolate HTML blocks
# --- Stateful Filtering ---
# Stack to track frame IDs of functions we are interested in.
# This allows tracing nested calls within a filtered function.
interest_stack = []


def is_allowed_file(filename):
    """Checks if a file is within the allowed paths for tracing.

    This function determines if the given filename's absolute path starts with any of the
    configured allowed paths. This is used to filter which files are traced.

    Args:
        filename (str): The path to the file.

    Returns:
        bool: True if the file is within an allowed path, False otherwise.
    """
    if not filename or not os.path.isabs(filename):
        return False

    filename = os.path.abspath(filename)
    return any(filename.startswith(path) for path in ALLOWED_PATHS)


def safe_repr(value):
    """Returns a safe representation of a value, handling potential exceptions.

    This function attempts to get the string representation of a value using repr().
    If any exception occurs during this process, it returns a string indicating
    that the value is unrepresentable, along with the exception message.

    Args:
        value: The value to represent.

    Returns:
        str: The string representation of the value, or an error message if representation fails.
    """
    try:
        return repr(value)
    except Exception as e:
        return f"<unreprable: {e}>"


def html_log_init():
    """Initializes the HTML log file.

    This function creates the HTML log file (trace_log.html) if it doesn't exist.
    It writes the basic HTML structure, including CSS styles for different log message types,
    JavaScript for interactive elements (expanding/collapsing sections), and initial content
    like system information and trace settings. It also adds sections for allowed/blocked paths
    and modules, fetched from the configuration.
    """

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
    function toggleCalls(show) {{
        const calls = document.querySelectorAll("details.call");
        calls.forEach(d => d.open = show);
    }}
    </script>
</head>
<body>
<div style="margin-bottom: 1em;">
    <button onclick="toggleAll(true)">📂 Expand All</button>
    <button onclick="toggleAll(false)">📁 Collapse All</button>
    <button onclick="toggleCalls(true)">📞 Expand Calls</button>
    <button onclick="toggleCalls(false)">🔕 Collapse Calls</button>
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


def log(msg, style_class=None, raw_html=False):
    """Logs a message to both the text and HTML log files.

    This function prints the given message to the console and appends it to both the plain text
    log file (trace_log.txt) and the HTML log file (trace_log.html). It handles UnicodeEncodeErrors
    gracefully and applies HTML formatting (escaping special characters, adding CSS classes)
    as needed. It also allows for logging raw HTML directly.

    Args:
        msg (str): The message to log.
        style_class (str, optional): The CSS class to apply to the message in the HTML log. Defaults to None.
        raw_html (bool, optional): Whether the message is raw HTML and should not be escaped. Defaults to False.
    """

    print(msg)

    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except UnicodeEncodeError:
        msg = msg.encode('ascii', errors='replace').decode('ascii')
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')

    if raw_html:
        html_line = msg  # do not escape or wrap
    else:
        html_line = msg.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if style_class:
            html_line = f'<span class="{style_class}">{html_line}</span>'
        html_line += "<br>"

    with open(HTML_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(html_line + '\n')


def trace_calls(frame, event, arg):
    """Traces function calls, lines, and returns, logging details to files.

    This function acts as the trace function for sys.settrace, receiving events about function calls,
    line executions, and returns. It filters events based on configuration settings (allowed/blocked paths,
    modules, function/file name filters), logs relevant information (function name, file, line number,
    local variables, return values, execution time) to both text and HTML log files, and manages
    tracing within nested function calls.

    Args:
        frame (frame): The current stack frame.
        event (str): The type of event ('call', 'line', 'return').
        arg: An argument specific to the event type.

    Returns:
        function: The trace_calls function itself to continue tracing within the current scope, or None to stop tracing.
    """
    code = frame.f_code
    filename = code.co_filename
    module_name = frame.f_globals.get('__name__', '')
    func_name = code.co_name

    # --- Venv Filtering ---
    # Immediately ignore anything inside a virtual environment directory.
    if any(f"/{venv_path}/" in filename.replace('\\', '/') for venv_path in VENVS):
        return None

    # --- Filtering Logic ---
    # CRITICAL: First, check if the file is allowed. If not, return immediately
    # to keep the tracer alive. Do NOT perform any other operations like relpath,
    # as they can fail on external/system files and kill the trace for the thread.
    if not is_allowed_file(filename):
        return trace_calls

    rel_path = os.path.relpath(filename, cfg_mgr.app_root_path('')).replace('\\', '/')

    # Apply general path/module filters.
    if any(block in rel_path for block in BLOCKED_PATHS): return trace_calls
    if any(module_name.startswith(block) for block in BLOCKED_MODULES): return trace_calls
    if FILE_FILTERS and not any(f in rel_path for f in FILE_FILTERS): return trace_calls

    line_no = frame.f_lineno
    now = datetime.now().strftime('%H:%M:%S')
    frame_id = id(frame)

    # --- Stateful Function Filtering ---
    is_currently_tracing = bool(interest_stack)
    # Check if the current function is an entry point if we are not already tracing.
    is_entry_point = not FUNC_FILTERS or any(f in func_name for f in FUNC_FILTERS)

    if event == 'call':
        # If we are not already in an interesting call stack, and this function is not an entry point, skip it.
        if not is_currently_tracing and not is_entry_point:
            return trace_calls # Keep tracing, but ignore this branch.

        # This is either an entry point or a nested call inside one. Start tracing it.
        interest_stack.append(frame_id)

        if TRACE_CALLS:
            try:
                with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                    current_line = f.readlines()[line_no - 1].strip()
            except Exception:
                current_line = "<source not available>"

            call_times[frame_id] = time.time()
            last_locals[frame_id] = frame.f_locals.copy()
            log(f'<details class="call" open><summary>[{now}] 📞 CALL: {func_name}() at {rel_path}:{line_no}</summary>', raw_html=True)
            log(f"<pre>    >> {current_line}", "line", raw_html=True)
            if TRACE_VARS and last_locals[frame_id]:
                local_vars_str = ", ".join(f"{k}={safe_repr(v)}" for k, v in last_locals[frame_id].items())
                log(f"    🧠 Locals: {local_vars_str}", "locals")

    elif event == 'line':
        # Only log lines if we are inside a function of interest.
        if is_currently_tracing and TRACE_LINES:
            try:
                with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                    current_line = f.readlines()[line_no - 1].strip()
            except Exception:
                current_line = "<source not available>"
            log(f"[{now}] 📍 LINE: {rel_path}:{line_no} -> {current_line}", "line")

            if TRACE_VARS:
                current = frame.f_locals.copy()
                previous = last_locals.get(frame_id, {})
                changes = []
                for k, v in current.items():
                    prev_v = previous.get(k, object())  # Use a unique default object

                    # Determine if a comparison is needed and how to do it safely
                    is_different = False
                    # Use array_equal if either is a numpy array to avoid ValueError
                    if isinstance(v, np.ndarray) or isinstance(prev_v, np.ndarray):
                        # This can still fail if one is an array and the other is not comparable
                        try:
                            if not np.array_equal(v, prev_v):
                                is_different = True
                        except (TypeError, ValueError):
                            is_different = True # Treat comparison failure as a difference
                    else:
                        # General comparison for all other types, with a safety net
                        try:
                            if v != prev_v:
                                is_different = True
                        except Exception: # Catch errors from complex object comparisons (e.g., closed shelves)
                            is_different = True # Assume different if comparison fails
                    if is_different:
                        changes.append(f"{k} = {safe_repr(v)}")
                if changes:
                    log("    🔄 Changes: " + ", ".join(changes), "locals")
                last_locals[frame_id] = current

    elif event == 'return':
        # Check if the returning frame is one we were tracing.
        if frame_id in interest_stack:
            # It's possible for a function to be on the stack multiple times (recursion).
            # We pop until we find the matching frame_id to correctly handle the stack.
            while interest_stack and interest_stack[-1] != frame_id:
                interest_stack.pop()
            if interest_stack:
                interest_stack.pop()

            if TRACE_CALLS:
                duration = time.time() - call_times.pop(frame_id, time.time())
                log(f"    ✅ RETURN from {func_name}() -> {safe_repr(arg)} (after {duration:.4f}s)", "return")
                log("</pre></details>", raw_html=True)
            last_locals.pop(frame_id, None)

    # Always return the tracer function to continue tracing.
    return trace_calls


html_log_init()
sys.settrace(trace_calls)
threading.settrace_all_threads(trace_calls)
