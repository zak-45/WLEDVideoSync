from coldtype import *
from coldtype.raster import *

# fnt = Font.List("")
# fnt = Font.Find("Roboto Serif 20pt")

states = [
    dict(wdth=0, rotate=-10),
    dict(wdth=1, rotate=15),
    dict(wdth=0.5, rotate=-90),
    dict(wdth=1, rotate=-25),
    dict(wdth=1, rotate=0)
]

spacings = [
    dict(tu=300),
    dict(tu=80),
    dict(tu=330),
    dict(tu=150),
    dict(tu=80),
]

at = AsciiTimeline(3, 25, """
                                <
[0     ][1     ][2     ][3     ][4     ]
""").shift("end", -10)

def list_fonts_skia():
    """
    List fonts using Skia's FontMgr.

    Returns:
    - A sorted list of font family names.
    """
    font_mgr = skia.FontMgr()
    fonts = []
    fonts.extend(
        font_mgr.getFamilyName(i) for i in range(font_mgr.countFamilies())
    )
    print(fonts)
    return sorted(fonts)

fnt_list = Font.List(" ")

fnt_path = Font.Cacheable('C:/Windows/Fonts/NotoSans-Regular.ttf')


@animation(Rect(860, 320), timeline=at, bg=-1)
def default(f):

    state = at.kf("eeio", keyframes=states)
    spacing = at.kf("seio", keyframes=spacings)

    # Calculate scrolling position
    scroll_speed = 20  # Pixels per frame
    x_position = 1080 - (f.i * scroll_speed)  # Start at the right and move left

    gen_image = (StSt("WLEDVideoSync", fnt_path,
        200, fill=0, **{**state, **spacing}, r=1, leading=80)
        .align(f.a.r)
        .translate(x_position, 0)  # Scroll horizontally
        .f(hsl(1.0, s=0.75))
        .chain(rasterized(f.a.r, wrapped=False))  # Get skia.Image
    )

    print(type(gen_image))

    return SkiaImage(gen_image)