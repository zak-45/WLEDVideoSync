import cv2
from src.txt.textanimator import TextAnimator
from src.utl.cv2utils import CV2Utils as ImgUtils
from src.utl.utils import CASTUtils as Utils

sl, w, h = Utils.attach_to_manager_queue('Thread-4 (t_desktop_cast)_q')

# Example 16: Exploding text with pre-delay
animator = TextAnimator(
    text="W L E D",
    width=800,
    height=320,
    speed=0,  # No scrolling for this example
    alignment='center',
    direction='up', # up or down to stay fit
    color=(38,201,38),  #
    fps=15,
    font_path=r"C:\Windows\Fonts\TT1023M_.TTF",  # Replace with your font path
    font_size=350,
    effect="explode",
    explode_speed=15,  # Adjust explosion speed as needed
    explode_pre_delay=2 # Delay before explosion in seconds
)

for _ in range(150):  # Adjust number of frames as needed
    frame = animator.generate()
    if frame is not None:
        if all(item is not None for item in [sl, w, h]):
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ImgUtils.send_to_queue(frame, sl, w, h)
        cv2.imshow("Exploding Text Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()

