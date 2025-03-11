import cv2
from coldtype import *
from coldtype.raster import *
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils as ImgUtils

sl, w, h = Utils.attach_to_manager_queue('Thread-9 (t_desktop_cast)_q')

# Define the string to cycle through
s = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Construct a timeline based on the string and a frame-count-per-element
frames_per_element = 20
clips = []

for idx, c in enumerate(s):
    start = idx * frames_per_element
    clips.append(Timeable(start, start + frames_per_element, idx, c))

timeline = Timeline(fps=30, timeables=clips)

# Define the colors
bg_color = hsl(0.6, s=1, l=0.5)  # blue background
text_color = hsl(0.08, s=1, l=0.5)  # orange text
info_text_color = hsl(0.5, s=0.5, l=0.5)  # color for info text

font = Font.Find("x")

@animation(rect=(1280, 640),timeline=timeline, bg=bg_color)  # adjust the timeline according to the animation animation_speed
def cold_demo_02(f):
    letter = timeline.at(f.i).now()
    t = letter.e("linear", 0)

    # Oscillate weight of each letter
    if letter.idx % 2 == 0:  # even letter index
        wght = letter.e("eeio", 0, rng=(0, 1))
    else:  # odd letter index
        wght = letter.e("eeio", 0, rng=(1, 0))

    # Create a new styled text object using the selected font and the calculated weight
    txt = (StSt(letter.name, font, 500, wght=wght)
           .align(f.a.r, tx=0)
           .f(text_color)
          
          )  # set the text color

    # Display info text
    info_text = (StSt(f"Index: {letter.idx}, Progress: {t:.2f}, Weight: {wght:.2f}", font, 50)
                 .pens()
                 .align(f.a.r.take(160, "S"), tx=0)
                 .f(info_text_color)

                )  # set the info text color

    # Return the styled text
    gen_image  = P(  
        P().rect(f.a.r).f(bg_color),  # set the background color
        txt,
        info_text) # add the info text

    frame = gen_image.ch(rasterized(f.a.r, wrapped=False))
    frame = frame.toarray()
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

    if all(item is not None for item in [sl, w, h]):
        ImgUtils.send_to_queue(frame, sl, w, h)    

    
    return gen_image
