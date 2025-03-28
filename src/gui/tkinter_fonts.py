import contextlib
import tkinter as tk
from tkinter import font
import platform

def run():
    def update_preview():
        """Update the preview text with the selected font and style."""
        try:
            selected_font = font_listbox.get(font_listbox.curselection())
            selected_style = style_var.get()

            # Map the style to weight and slant
            weight = "bold" if "Bold" in selected_style else "normal"
            slant = "italic" if "Italic" in selected_style else "roman"

            # Check if the font supports the selected style
            temp_font = font.Font(family=selected_font, size=12, weight=weight, slant=slant)
            if temp_font.actual("weight") != weight or temp_font.actual("slant") != slant:
                preview_label.config(
                    text=f"The font '{selected_font}' does not support the '{selected_style}' style."
                )
                return

            preview_font = font.Font(family=selected_font, size=16, weight=weight, slant=slant)
            preview_label.config(font=preview_font, text=f"WLEDVideoSync font Preview:\n {selected_font} ({selected_style})")
        except tk.TclError:
            preview_label.config(text="Font preview unavailable")

    def populate_styles(event):
        """Populate the styles dropdown based on the selected font."""
        with contextlib.suppress(tk.TclError):
            selected_font = font_listbox.get(font_listbox.curselection())

            # Define supported styles
            styles = ["Regular", "Bold", "Italic", "Bold Italic"]
            style_var.set("Regular")  # Reset to default style

            # Update the dropdown menu
            style_menu['menu'].delete(0, 'end')
            for style in styles:
                style_menu['menu'].add_command(label=style, command=lambda value=style: style_var.set(value))

            # Update the attributes label
            attributes_label.config(text=f"Attributes: Font: {selected_font}, Available Styles: {', '.join(styles)}")
            update_preview()

    def set_default_font():
        """Set the default font selection based on the operating system."""
        os_name = platform.system()
        default_font = "Arial"  # Fallback default

        if os_name == "Windows":
            default_font = "Segoe UI"
        elif os_name == "Darwin":  # macOS
            default_font = "Helvetica"
        elif os_name == "Linux":
            default_font = "DejaVu Sans"

        # Select the default font in the listbox
        if default_font in available_fonts:
            index = available_fonts.index(default_font)
            font_listbox.selection_set(index)
            font_listbox.see(index)
            populate_styles(None)

    def copy_to_clipboard():
        """Copy the font name, style to the clipboard."""
        try:
            selected_font = font_listbox.get(font_listbox.curselection())
            selected_style = style_var.get()

            # Format the clipboard text
            clipboard_text = f"Font: {selected_font}\nStyle: {selected_style}\nFont Path: Not available"

            # Copy to clipboard
            root.clipboard_clear()
            root.clipboard_append(clipboard_text)
            root.update()  # Ensure the clipboard content is updated

            # Show confirmation message
            preview_label.config(text="Font information copied to clipboard!")
        except tk.TclError:
            preview_label.config(text="Error copying font information.")


    # Create the main window
    root = tk.Tk()
    root.title("WLEDVideoSync Font Selector with Styles")
    root.geometry("800x600")

    # Create a frame for the font list
    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Add a label
    # label = tk.Label(frame, text="Available Fonts:", font=("Arial", 14))
    # label.pack(anchor=tk.W)

    # Add a button to copy font information to clipboard
    copy_button = tk.Button(frame, text="Copy Font Info", command=copy_to_clipboard)
    copy_button.pack(pady=5)

    # Add a scrollbar for the listbox
    scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Add a listbox to display the fonts
    font_listbox = tk.Listbox(frame, height=15, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set)
    font_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    scrollbar.config(command=font_listbox.yview)

    available_fonts = sorted(font.families())
    for f in available_fonts:
        font_listbox.insert(tk.END, f)

    # Add a label to display font attributes
    attributes_label = tk.Label(frame, text="", font=("Arial", 10), wraplength=400, justify=tk.LEFT)
    attributes_label.pack(pady=5)

    # Add a dropdown for styles
    style_var = tk.StringVar(value="Regular")
    style_menu = tk.OptionMenu(frame, style_var, "Regular")
    style_menu.pack(pady=5)

    # Add a label to preview the selected font
    preview_label = tk.Label(root, text="Select a font to preview", font=("Arial", 16), wraplength=400)
    preview_label.pack(pady=10, fill=tk.X, side=tk.BOTTOM)

    # Bind the listbox selection to populate styles
    font_listbox.bind("<<ListboxSelect>>", populate_styles)

    # Bind the dropdown menu to update the preview
    style_var.trace_add("write", lambda *args: update_preview())

    # Set the default font based on the OS
    set_default_font()

    # Run the main event loop
    root.mainloop()

if __name__ in "__main__":
    run()
