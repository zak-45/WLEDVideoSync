import tkinter as tk

# Create the main application window
root = tk.Tk()
root.title("Simple Text Display")

# Create a label widget to display text
label = tk.Label(root, text="Hello, World!", font=("Arial", 24))
label.pack(padx=20, pady=20)  # Add padding around the label

# Start the Tkinter event loop
root.mainloop()
