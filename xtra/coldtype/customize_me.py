import cv2
from src.txt.textanimator import TextAnimator

# Example 16: Exploding text with pre-delay
animator = TextAnimator(
    text="Exploding text with pre-delay",
    width=620,
    height=240,
    speed=0,  # No scrolling for this example
    direction="right",
    color=(0, 0, 255),  # Blue text
    fps=30,
    alignment='center',
    font_path="../../assets/Font/DejaVuSansCondensed.ttf",  # Replace with your font path
    font_size=60,
    effect="explode",
    explode_speed=10,  # Adjust explosion speed as needed
    explode_pre_delay=2 # Delay before explosion in seconds
)

for _ in range(150):  # Adjust number of frames as needed
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Exploding Text Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()

