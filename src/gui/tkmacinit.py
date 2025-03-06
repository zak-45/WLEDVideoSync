import sys
import tkinter as tk
from tkinter import PhotoImage
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger')

config_file = cfg_mgr.app_root_path('config/WLEDVideoSync.ini')

def init():
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
