import cv2
from src.txt.textanimator import TextAnimator

# Example 16: Exploding text with pre-delay
animator = TextAnimator(
    text="Wait & Explode",
    width=800,
    height=640,
    speed=0,  # No scrolling for this example
    alignment='center',
    direction='up', # up or down to stay fit
    color=(0, 0, 255),  # Blue text
    fps=60,
    font_path=r"‪‪‪‪‪‪C:\Windows\Fonts\TT1018M_.TTF",  # Replace with your font path
    font_size=50,
    effect="explode",
    explode_speed=10,  # Adjust explosion speed as needed
    explode_pre_delay=2 # Delay before explosion in seconds
)

for _ in range(250):  # Adjust number of frames as needed
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Exploding Text Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()

