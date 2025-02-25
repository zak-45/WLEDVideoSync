import cv2
from src.txt.textanimator import TextAnimator


# Example 1: Basic scrolling text
animator = TextAnimator(
    text="Basic scrolling text",
    width=640,
    height=120,
    speed=400,
    font_path="../../assets/Font/DejaVuSansCondensed.ttf",  # Replace with your font path
    font_size=60,
    direction="left",
    effect='particle',
    color=(255, 255, 255), # White text
    fps=30
)

for _ in range(200): # Generate 100 frames
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps)) # Delay to match FPS

cv2.destroyAllWindows()
animator.stop()


# Example 2: Scrolling text with custom font, color, and shadow
animator = TextAnimator(
    text="Scrolling text with custom font,\n color,\n and shadow",
    width=800,
    height=600,
    speed=100,
    direction="up",
    color=(0, 0, 255), # Blue text
    fps=24,
    font_path="../../assets/Font/DejaVuSansCondensed.ttf", # Replace with your font path
    font_size=40,
    shadow=True,
    shadow_color=(128, 128, 128), # Gray shadow
    shadow_offset=(2, 5)
)

for _ in range(200): # Generate 200 frames
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps))

cv2.destroyAllWindows()
animator.stop()

# Example 3: Basic scrolling blink text
animator = TextAnimator(
    text="Scrolling blink text",
    width=640,
    height=120,
    speed=400,
    font_path="../../assets/Font/DejaVuSansCondensed.ttf",  # Replace with your font path
    font_size=60,
    direction="left",
    effect="blink",
    blink_interval=.1,
    color=(0, 255, 255),
    fps=30
)

for _ in range(200): # Generate 200 frames
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps)) # Delay to match FPS

cv2.destroyAllWindows()
animator.stop()


# Example 4: color cycling
animator = TextAnimator(
    text="Scrolling color cycling text",
    width=640,
    height=120,
    speed=400,
    font_path="../../assets/Font/DejaVuSansCondensed.ttf",  # Replace with your font path
    font_size=60,
    direction="left",
    effect="color_cycle",
    color=(0, 255, 255),
    fps=30
)

for _ in range(200): # Generate 100 frames
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps)) # Delay to match FPS

cv2.destroyAllWindows()
animator.stop()

# Example 4: color cycling
animator = TextAnimator(
    text="Scrolling color cycling text",
    width=640,
    height=120,
    speed=400,
    font_path="../../assets/Font/DejaVuSansCondensed.ttf",  # Replace with your font path
    font_size=60,
    direction="left",
    effect="rainbow_cycle",
    color=(0, 255, 255),
    fps=30
)

for _ in range(200): # Generate 100 frames
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps)) # Delay to match FPS

cv2.destroyAllWindows()
animator.stop()


# Example 5: Fading text
animator = TextAnimator(
    text="Fading Text",
    width=700,
    height=300,
    speed=0, # No scrolling
    direction="left", # Direction doesn't matter when speed is 0
    color=(255, 0, 0), # Red text
    font_path="../../assets/Font/DejaVuSansCondensed.ttf",  # Replace with your font path
    font_size=60,
    fps=20,
    effect="fade",
    opacity=0.8 # Initial opacity
)

for _ in range(200):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps))

cv2.destroyAllWindows()
animator.stop()


# Example 6: Combining blink and color cycle effects
animator = TextAnimator(
    text="Blinking Color Cycling",
    width=600,
    height=200,
    speed=0,
    direction="left",
    color=(255, 255, 255),  # Initial color (will be cycled)
    fps=30,
    effect="blink", # Try also with just color_cycle, or fade
    # You can combine effects by initializing effect_params with multiple effect settings
)
animator.effect_params.update(animator.init_effect_params()) # re-initialize to add color cycle
animator.effect = "color_cycle" # set the effect to color cycle
animator.effect_params.update(animator.init_effect_params()) # re-initialize to add fade
animator.effect = "fade" # set the effect to fade


for _ in range(300):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps))

cv2.destroyAllWindows()
animator.stop()



# Example 7: Diagonal scrolling (requires modifying TextAnimator)
# In textanimator.py, modify initialize_scrolling and read methods to handle diagonal movement.
animator = TextAnimator(
    text="Diagonal Text",
    width=800,
    height=600,
    speed=80, # adjust speed as needed
    direction="down_right", # or "up_right", "down_left", "up_left"
    color=(255, 165, 0), # Orange
    fps=25
)

for _ in range(300):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps))

cv2.destroyAllWindows()
animator.stop()



# Example 8: Centered text
animator = TextAnimator(
    text="Centered Text",
    width=500,
    height=100,
    speed=50,
    direction="left",
    color=(255, 255, 0), # Yellow text
    fps=30,
    alignment="center" # or "right"
)

for _ in range(200):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps))

cv2.destroyAllWindows()
animator.stop()


# Example 9: Background color
animator = TextAnimator(
    text="With Background",
    width=600,
    height=200,
    speed=75,
    direction="right",
    color=(0, 0, 0), # Black text
    fps=30,
    bg_color=(0, 255, 255) # Light blue background
)

for _ in range(300):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()


# Example 10: Custom blink interval
animator = TextAnimator(
    text="Slower Blink",
    width=500,
    height=100,
    speed=0,
    direction="left",
    color=(255, 0, 255), # Magenta
    fps=30,
    effect="blink",
    blink_interval=2 # Blink every 2 seconds (adjust as needed)

)

for _ in range(300):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000/animator.fps))

cv2.destroyAllWindows()
animator.stop()


# Example 11: Using a specific font size
animator = TextAnimator(
    text="Font Size Example",
    width=800,
    height=200,
    speed=50,
    direction="right",
    color=(0, 128, 0),  # Green
    fps=30,
    font_size=48,  # Specify font size
)

for _ in range(300):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()


# Example 12: Transparent background with opacity
animator = TextAnimator(
    text="Transparent Background",
    width=700,
    height=150,
    speed=60,
    direction="left",
    color=(255, 0, 255),  # Magenta
    fps=25,
    opacity=0.7,  # Set opacity (0.0 - 1.0)
)

for _ in range(250):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()



# Example 13: Right-aligned text
animator = TextAnimator(
    text="Right Aligned",
    width=600,
    height=100,
    speed=40,
    direction="up",  # Vertical scrolling
    color=(0, 255, 255),  # Cyan
    fps=30,
    alignment="right",
)

for _ in range(300):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()



# Example 14: Combining shadow with fade effect
animator = TextAnimator(
    text="Shadow Fade",
    width=800,
    height=250,
    speed=0,  # No scrolling
    direction="left",
    color=(255, 255, 0),  # Yellow
    fps=20,
    effect="fade",
    shadow=True,
    shadow_color=(100, 100, 100),  # Dark gray shadow
    shadow_offset=(4, 4),
    opacity=0.9,  # Initial opacity
)

for _ in range(200):
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()



# Example 15: Pausing the animation

animator = TextAnimator(
    text="Pausing Animation",
    width=640,
    height=100,
    speed=70,
    direction="left",
    color=(128, 0, 128),  # Purple
    fps=30,
)

for i in range(300):
    if i == 100:  # Pause at frame 100
        animator.pause()
    elif i == 200:  # Resume at frame 200
        animator.resume()

    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()

# Example for rainbow cycle effect:

animator = TextAnimator(
    text="Rainbow Text!",
    width=800,
    height=200,
    speed=0,  # No scrolling for this example
    direction="left",
    color=(0, 0, 0),  # Initial color (will be overwritten by the effect)
    fps=30,
    effect="rainbow_cycle"
)

for _ in range(600):  # Display for 20 seconds (600 frames at 30fps)
    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Rainbow Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()


# Example 16: Exploding text with pre-delay
animator = TextAnimator(
    text="Exploding text with pre-delay",
    width=620,
    height=120,
    speed=0,  # No scrolling for this example
    direction="right",
    color=(0, 0, 255),  # Blue text
    fps=30,
    alignment='center',
    font_path="../../assets/Font/DejaVuSansCondensed.ttf",  # Replace with your font path
    font_size=40,
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

