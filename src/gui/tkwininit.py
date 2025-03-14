"""
a: zak-45
d: 07/03/2025
v: 1.0.0.0

Overview
This Python script (tkwininit.py) creates a simple graphical user interface (GUI) window using Tkinter.
Its primary purpose is to display information to the user after the application's executable has been extracted.
It informs the user about the successful extraction, instructs them on how to run the application, and displays a
disclaimer about the software's usage. The window then closes when the user clicks an "Ok" button, and the script exits.

Key Components
init() function:
    This function initializes and displays the main GUI window.
    It handles window creation, setting the title, size, background color, and icon.
    It also defines the informational text displayed within the window and the behavior of the "Ok" button.

on_ok_click() function:
    This function is called when the "Ok" button is clicked.
    Its sole purpose is to close the main window using root.destroy().

ConfigManager:
    An instance of ConfigManager is used to access paths, specifically for loading the configuration file
    ('WLEDVideoSync.ini') and the application icon ('favicon.png').

Tkinter elements:
    The script uses standard Tkinter widgets like tk.Tk() for the main window, tk.Label to display the information text,
    and tk.Button for the "Ok" button. These are used to create the simple GUI.

Informational Text:
    The script displays a multi-line message providing instructions and a disclaimer to the user.
    This message is the core purpose of the GUI window.

sys.exit():
    After the window is closed, the script calls sys.exit() to terminate the Python process.
    This ensures the script doesn't continue running in the background after the window is closed.

"""

import sys
import tkinter as tk
from tkinter import PhotoImage
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger')

config_file = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')

def init():
    """Display an informational window after executable extraction.

    Informs the user about the successful extraction, provides
    instructions on running the application, and shows a disclaimer.
    """
    def on_ok_click():
        # Close the window when OK button is clicked
        root.destroy()

    # Create the main window
    root = tk.Tk()
    root.title("WLEDVideoSync Information")
    root.geometry("800x460")  # Set the size of the window
    root.configure(bg='#657B83')  # Set the background color

    # Change the window icon
    icon = PhotoImage(file=cfg_mgr.app_root_path('favicon.png'))
    root.iconphoto(False, icon)

    # Define the window's contents
    info_text = ("Extracted executable to WLEDVideoSync folder.....\n\n \
    You can safely delete this file after extraction finished to save some space.\n \
    (the same for WLEDVideoSync.out.txt and err.txt if there ...)\n\n \
    Go to WLEDVideoSync folder and run WLEDVideoSync-{OS} file\n \
    This is a portable version, nothing installed on your system and can be moved where wanted.\n\n \
    Enjoy using WLEDVideoSync\n\n \
    -------------------------------------------------------------------------------------------------\n \
    THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,\n \
    INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n \
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.\n \
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,\n \
    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n \
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n \
    -------------------------------------------------------------------------------------------------\n ")

    info_label = tk.Label(root, text=info_text, bg='#657B83', fg='white', justify=tk.LEFT)
    info_label.pack(padx=10, pady=10)

    # Create the OK button
    ok_button = tk.Button(root, text="Ok", command=on_ok_click, bg='gray', fg='white')
    ok_button.pack(pady=10)

    # Start the Tkinter event loop
    root.mainloop()

    sys.exit()

if __name__ == "__main__":
    init()