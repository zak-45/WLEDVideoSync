import tkinter as tk
from tkinter import font
import matplotlib.font_manager as fm
import os


def on_font_selected(font_name):
    print("Selected font:", font_name)


def show_fonts():
    root = tk.Tk()
    root.title("Available Fonts")

    fonts = font.families()
    initial_font = fonts[0]  # Select the first font by default

    selected_font = tk.StringVar(value=initial_font)

    canvas = tk.Canvas(root)
    scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    font_frame = tk.Frame(canvas)

    font_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=font_frame, anchor="nw")

    canvas.configure(yscrollcommand=scrollbar.set)

    system_fonts_ttf = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    system_fonts_otf = fm.findSystemFonts(fontpaths=None, fontext='otf')
    system_fonts = system_fonts_ttf + system_fonts_otf

    for f in fonts:
        font_info = font.Font(font=(f, 12))
        style = font_info.actual()['slant']
        weight = font_info.actual()['weight']
        size = font_info.actual()['size']

        frame = tk.Frame(font_frame)

        radiobutton = tk.Radiobutton(frame, variable=selected_font, text=f, value=f,
                                     command=lambda f=f: on_font_selected(f))
        radiobutton.pack(side="left", padx=5)

        label = tk.Label(frame,
                         text=f"Style: {style}, "
                              f"Weight: {weight}, "
                              f"Size: {size}, "
                              f"Extension: {get_font_extension(system_fonts, f)}",
                         font=("Arial", 10))
        label.pack(side="left", padx=5)

        label_preview = tk.Label(frame, text="WLEDVideoSync Text", font=(f, 12))
        label_preview.pack(side="left", padx=5)

        frame.pack(fill="both", padx=5, pady=2)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    root.mainloop()


def get_font_extension(system_fonts, font_name):
    for font_path in system_fonts:
        base_name = os.path.basename(font_path)
        if font_name.lower() in base_name.lower():
            _, extension = os.path.splitext(base_name)
            return extension
    return "Unknown"


show_fonts()
