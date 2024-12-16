"""
a: zak-45
d: 03/12/2024
v: 1.0.0.0

 Tkinter info window

"""

import tkinter as tk
import sys

def show_message(message, msg_type: str = ''):
    """
    Create a Tkinter window to inform the user.
    msg_type : define bg color --> red for error
    This function initializes a Tkinter window with a message informing the user. It includes an 'OK' button
    to dismiss the message.
    """
    root = tk.Tk()
    root.title("WLEDLipSync Information")
    bg_color = 'red' if msg_type == 'error' else '#0E7490'
    root.configure(bg=bg_color)  # Set the background color
    label = tk.Label(root, text=message, bg=bg_color, fg='white', justify=tk.LEFT, padx=20, pady=20)
    label.pack()

    # Create an OK button to close the window
    ok_button = tk.Button(root, text="OK", command=root.destroy)
    ok_button.pack(pady=10)

    # Make the window stay on top of other windows
    root.attributes('-topmost', True)
    if sys.platform.lower() == 'win32':
        root.attributes('-toolwindow', True)
    elif sys.platform.lower() == 'linux':
        root.attributes('-type', 'notification')
    elif sys.platform.lower() == 'darwin':
        root.attributes('-notify', True)

    # Start the Tkinter event loop
    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) > 2:
        show_message(sys.argv[1], sys.argv[2])
