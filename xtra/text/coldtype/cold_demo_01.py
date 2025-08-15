import cv2
from coldtype import *
from coldtype.raster import *
from src.utl.utils import CASTUtils as Utils
from src.utl.cv2utils import CV2Utils as ImgUtils

sl, w, h = Utils.attach_to_manager_queue('Thread-9 (t_desktop_cast)_q')

@animation((800, 240), timeline=100, bg=hsl(.9))
def cold_demo_01(f):

    gen_image = (StSt("CDELOPTY",
        Font.ColdtypeObviously(), 150,
        wdth=f.e("eeio", 1))
        .align(f.a.r)
        .f(1)
        .chain(rasterized(f.a.r, wrapped=False))  # Get skia.Image   
           )

    frame = gen_image.toarray()
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

    if all(item is not None for item in [sl, w, h]):
        ImgUtils.send_to_queue(frame, sl, w, h)

    return SkiaImage(gen_image)
