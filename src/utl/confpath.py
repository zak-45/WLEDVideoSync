import os
import sys


def get_resource_path(filename):
    """Returns the correct path for resources, handling different OS structures."""

    if getattr(sys, 'frozen', False):  # Running from a compiled binary (Nuitka, PyInstaller)
        if sys.platform == "darwin":  # macOS
            base_path = os.path.dirname(os.path.dirname(sys.executable))  # Contents/
            return os.path.join(base_path, "MacOS", filename)
        else:  # Windows/Linux (Nuitka puts files in the same dir as the binary)
            base_path = os.path.dirname(sys.executable)
            return os.path.join(base_path, filename)

    # Running in development mode (not compiled)
    return os.path.abspath(filename)

