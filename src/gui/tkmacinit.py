"""
a: zak-45
d: 07/03/2025
v: 1.0.0.0

Overview
This Python script (tkmacinit.py) displays an informational window on macOS after initial setup of the WLEDVideoSync application.
It informs the user that the setup is complete, describes the portable nature of the application, and presents
a disclaimer about the software's warranty. The script then exits, effectively ending its own execution.

Key Components
init() function:
    This function is the main entry point of the script.
    It creates the main window, sets its properties (title, size, background color, icon), displays the information text,
    and creates an "OK" button to close the window.

on_ok_click() function:
    This function is called when the "OK" button is clicked. It simply closes the main window.

ConfigManager:
    Used to manage configuration settings, specifically to retrieve paths relative to the application's root directory,
    such as the path to the configuration file ('WLEDVideoSync.ini') and the application icon ('favicon.png').

tkinter library:
    Used for creating the graphical user interface elements, including the main window, label, and button.
    The script uses tk.Tk() to create the main window, tk.Label() to display the information, and tk.Button() for the "OK" button.

sys.exit():
    Called after the user closes the information window, terminating the script's execution.
    This script is invoked once during the initial setup process and is not a persistent part of the application's runtime.

"""


import sys
import tkinter as tk
from tkinter import PhotoImage

from configmanager import cfg_mgr

def init():
    """Display an informational window on macOS after initial setup.

    Informs the user about the completed setup, the portable nature
    of the application, and displays a software disclaimer.
    """
    def on_ok_click():
        # Close the window when OK button is clicked
        root.destroy()

    # Create the main window
    root = tk.Tk()
    root.title("WLEDVideoSync Information")
    root.geometry("840x400")  # Set the size of the window
    root.configure(bg='#657B83')  # Set the background color

    # Change the window icon
    icon = PhotoImage(file=cfg_mgr.app_root_path('favicon.png'))
    root.iconphoto(False, icon)

    # Define the window's contents
    info_text = ("Initial settings done for MacOS\n\n"
                 "This is a portable version, nothing installed on your system and can be moved where wanted.\n\n"
                 " Enjoy using WLEDVideoSync\n\n \
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