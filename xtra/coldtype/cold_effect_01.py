from coldtype import *
from coldtype.raster import *
from src.utl.sharedlistclient import SharedListClient
from src.utl.cv2utils import CV2Utils as img_utils
import time

client = SharedListClient()
client.connect()
sl = client.attach_to_shared_list('Thread-21 (t_desktop_cast)')
sl_info = client.get_shared_list_info('Thread-21 (t_desktop_cast)')

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

fps=15

at = AsciiTimeline(3, fps, """
                                <
[0     ][1     ][2     ][3     ][4     ]
""").shift("end", -10)

fnt_path = Font.Cacheable('assets/Font/DejaVuSansCondensed.ttf')

@animation(Rect(860, 220), timeline=at, bg=rgb(0,0,0,0))
def cold_effect_01(f):
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

    #print(sl[0])
    #sl[0] += 1

    return SkiaImage(gen_image)
