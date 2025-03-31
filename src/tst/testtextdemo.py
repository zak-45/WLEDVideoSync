"""
Required Parameters:
•text: The text string to be displayed.
•width: The width of the text image.
•height: The height of the text image.
•speed: The scrolling speed (pixels per frame).
•direction: The scrolling direction ("left", "right", "up", "down", "up_left", "down_right").
•color: The text color (a tuple of (B, G, R) values).
•fps: The frames per second for the animation.

Optional Parameters:
•font_path: The path to the font file (default: None).
•font_size: The font size (default: None).
•bg_color: The background color (a tuple of (B, G, R) values) (default: None).
•opacity: The opacity of the text (0.0 to 1.0) (default: 1.0).
•effect: The text effect to apply (e.g., "blink","color_cycle", "rainbow_cycle", "wave", "shake", "scale", "rotate",
                                    "slide_in", "zoom", "fade", "particle", "explode") (default: None).
•alignment: The text alignment ("left", "center", "right") (default: "center").
•shadow: Whether to draw a shadow (True/False) (default: False).
•shadow_color: The shadow color (a tuple of (B, G, R) values) (default: (0, 0, 0)).
•shadow_offset: The shadow offset (a tuple of (x, y) values) (default: (2, 2)).
•explode_speed: The speed of the explode effect (default: 10).
•blink_interval: The blink interval (in seconds) (default: 0.5).
•color_change_interval: The color change interval (in seconds) (default: 0.5).
•explode_pre_delay: The pre-delay before the explode effect starts (in seconds) (default: 0.5).

"""

import cv2
from src.txt.textanimator import TextAnimator


def show_animation(animator, num_frames=200, window_name="Animation"):
    """Helper function to display the animation."""
    for _ in range(num_frames):
        frame = animator.generate()
        if frame is not None:
            cv2.imshow(window_name, frame)
            cv2.waitKey(int(1000 / animator.fps))
    cv2.destroyAllWindows()
    animator.stop()


# Common parameters for all animations
common_params = {
    "text": "WLEDVideoSync ROCK !",
    "width": 800,
    "height": 200,
    "font_path": "../../assets/Font/DejaVuSansCondensed.ttf",
    "font_size": 60,
    "color": (255, 255, 255),  # White text
    "fps": 30,
    "speed": 100,
    "direction": "left"
}

# 1. Basic Scrolling (Left)
animator = TextAnimator(
    **common_params,
)
animator.speed = 100
show_animation(animator, window_name="Scrolling Left")

# 2. Basic Scrolling (Up)
animator = TextAnimator(
    **common_params,
)
animator.speed = 100
animator.direction = "up"
show_animation(animator, window_name="Scrolling Up")

# 3. Blink Effect
animator = TextAnimator(
    **common_params,
    effect="blink",
    blink_interval=.1,
)
animator.text = "Scrolling blink text"
animator.color = (0, 255, 255)
show_animation(animator, window_name="Blink Effect")

# 4. Color Cycle Effect
animator = TextAnimator(
    **common_params,
    effect="color_cycle",
)
show_animation(animator, window_name="Color Cycle Effect")

# 5. Rainbow Cycle Effect
animator = TextAnimator(
    **common_params,
    effect="rainbow_cycle",
)

show_animation(animator, window_name="Rainbow Cycle Effect", num_frames=300)

# 6. Wave Effect
animator = TextAnimator(
    **common_params,
    effect="wave",
)
animator.color = (0, 255, 0)
show_animation(animator, window_name="Wave Effect")

# 7. Shake Effect
animator = TextAnimator(
    **common_params,
    effect="shake",
)
animator.color = (255, 0, 255)
show_animation(animator, window_name="Shake Effect")

# 8. Scale Effect
animator = TextAnimator(
    **common_params,
    effect="scale",
)
animator.color = (0, 0, 255)
show_animation(animator, window_name="Scale Effect")

# 9. Rotate Effect
animator = TextAnimator(
    **common_params,
    effect="rotate",
)
animator.color = (255, 255, 0)
show_animation(animator, window_name="Rotate Effect")

# 10. Slide In Effect
animator = TextAnimator(
    **common_params,
    effect="slide_in",
)
animator.color = (255, 165, 0)
show_animation(animator, window_name="Slide In Effect")

# 11. Zoom Effect
animator = TextAnimator(
    **common_params,
    effect="zoom",
)
animator.color = (128, 0, 128)
show_animation(animator, window_name="Zoom Effect")

# 12. Fade Effect
animator = TextAnimator(
    **common_params,
    effect="fade",
    opacity=0.8,
)
animator.color = (255, 0, 0)
show_animation(animator, window_name="Fade Effect")

# 13. Particle Effect
animator = TextAnimator(
    **common_params,
    effect="particle",
)
animator.color = (0, 128, 0)
show_animation(animator, window_name="Particle Effect")

# 14. Explode Effect
animator = TextAnimator(
    **common_params,
    effect="explode",
    explode_speed=10,
    explode_pre_delay=1,
)
animator.color = (0, 0, 255)
show_animation(animator, window_name="Explode Effect", num_frames=150)

# 15. Diagonal Scrolling (Down Right)
animator = TextAnimator(
    **common_params,
)
animator.speed = 80
animator.direction = "down_right"
animator.color = (255, 165, 0)
show_animation(animator, window_name="Diagonal Scrolling (Down Right)", num_frames=300)

# 16. Diagonal Scrolling (Up Left)
animator = TextAnimator(
    **common_params,
)
animator.speed = 80
animator.direction = "up_left"
animator.color = (255, 165, 0)
show_animation(animator, window_name="Diagonal Scrolling (Up Left)", num_frames=300)

# 17. Centered Text
animator = TextAnimator(
    **common_params,
    alignment="center",
)
animator.speed = 50
animator.color = (255, 255, 0)
show_animation(animator, window_name="Centered Text")

# 18. Right-Aligned Text
animator = TextAnimator(
    **common_params,
    alignment="right",
)
animator.speed = 40
animator.direction = "up"
animator.color = (0, 255, 255)
show_animation(animator, window_name="Right-Aligned Text")

# 19. Shadow Effect
animator = TextAnimator(
    **common_params,
    shadow=True,
    shadow_color=(128, 128, 128),  # Gray shadow
    shadow_offset=(2, 5),
)
show_animation(animator, window_name="Shadow Effect")

# 20. Background Color
animator = TextAnimator(
    **common_params,
    speed=75,
    direction="right",
    bg_color=(0, 255, 255),  # Light blue background
    color=(0, 0, 0),  # Black text
)
show_animation(animator, window_name="Background Color", num_frames=300)

# 21. Transparent Background
animator = TextAnimator(
    **common_params,
    speed=60,
    opacity=0.7,
    color=(255, 0, 255),  # Magenta
)
show_animation(animator, window_name="Transparent Background", num_frames=250)

# 22. Pausing the animation
animator = TextAnimator(
    **common_params,
    speed=70,
    color=(128, 0, 128),  # Purple
)
for i in range(300):
    if i == 100:  # Pause at frame 100
        animator.pause()
    elif i == 200:  # Resume at frame 200
        animator.resume()

    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Pausing Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()

# 23. Combining shadow with fade effect
animator = TextAnimator(
    **common_params,
    effect="fade",
    shadow=True,
    shadow_color=(100, 100, 100),  # Dark gray shadow
    shadow_offset=(4, 4),
    opacity=0.9,  # Initial opacity
    color=(255, 255, 0),  # Yellow
)
show_animation(animator, window_name="Shadow Fade", num_frames=200)

# 24. Combining blink and color cycle effects
animator = TextAnimator(
    **common_params,
    effect="blink",  # Try also with just color_cycle, or fade
)
animator.effect_params.update(animator.init_effect_params())  # re-initialize to add color cycle
animator.effect = "color_cycle"  # set the effect to color cycle
animator.effect_params.update(animator.init_effect_params())  # re-initialize to add fade
animator.effect = "fade"  # set the effect to fade
show_animation(animator, window_name="Blinking Color Cycling", num_frames=300)
