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


def show_animation(my_animator, num_frames=250, window_name="Animation"):
    """Helper function to display the animation."""
    for _ in range(num_frames):
        my_frame = my_animator.generate()
        if my_frame is not None:
            cv2.imshow(window_name, my_frame)
            cv2.waitKey(int(1000 / my_animator.fps))
    cv2.destroyAllWindows()
    my_animator.stop()


# Common parameters for all animations
common_params = {
    "text": "WLEDVideoSync ROCK !",
    "width": 320,
    "height": 320,
    "font_path": "../../assets/Font/DejaVuSansCondensed.ttf",
    "font_size": 180,
    "color": (255, 255, 255),  # White text
    "fps": 25,
    "speed": 250,
    "direction": "left"
}

# 1. Basic Scrolling (Left)
animator = TextAnimator(
    **common_params,
)
show_animation(animator, window_name="Scrolling Left")

# 2. Basic Scrolling (Up)
animator = TextAnimator(
    **common_params,
)
animator.text = "Wled"
animator.speed = 100
animator.font_size=140
animator.direction = "up"
animator.apply()
show_animation(animator, window_name="Scrolling Up")

# 3. Blink Effect
animator = TextAnimator(
    **common_params,
    effect="blink",
    blink_interval=.1,
)
animator.text = "Scrolling blink text"
animator.color = (0, 255, 255)
animator.apply()
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
animator.apply()
show_animation(animator, window_name="Wave Effect")

# 7. Shake Effect
animator = TextAnimator(
    **common_params,
    effect="shake",
)
animator.color = (255, 0, 255)
animator.apply()
show_animation(animator, window_name="Shake Effect")

# 8. Scale Effect
animator = TextAnimator(
    **common_params,
    effect="scale",
)
animator.color = (0, 0, 255)
animator.apply()
show_animation(animator, window_name="Scale Effect")


# 13. Particle Effect
animator = TextAnimator(
    **common_params,
    effect="particle",
)
animator.color = (0, 128, 0)
animator.apply()
show_animation(animator, window_name="Particle Effect")

# 14. Explode Effect
animator = TextAnimator(
    **common_params,
    effect="explode",
    explode_speed=10,
    explode_pre_delay=1,
)
animator.color = (0, 0, 255)
animator.apply()
show_animation(animator, window_name="Explode Effect", num_frames=150)


# 17. Centered Text
animator = TextAnimator(
    **common_params,
    alignment="center",
)
animator.speed = 50
animator.color = (255, 255, 0)
animator.apply()
show_animation(animator, window_name="Centered Text")

# 18. Right-Aligned Text
animator = TextAnimator(
    **common_params,
    alignment="right",
)
animator.speed = 40
animator.direction = "up"
animator.color = (0, 255, 255)
animator.apply()
show_animation(animator, window_name="Right-Aligned Text")

# 19. Shadow Effect
animator = TextAnimator(
    **common_params,
    shadow=True,
    shadow_color=(128, 128, 128),  # Gray shadow
    shadow_offset=(2, 5),
)
animator.apply()
show_animation(animator, window_name="Shadow Effect")

# 20. Background Color
animator = TextAnimator(
    **common_params,
    bg_color=(0, 255, 255),  # Light blue background

)
animator.speed = 300
animator.direction="right"
animator.color = (255, 0, 255)
animator.apply()
show_animation(animator, window_name="Background Color", num_frames=450)


# 21. Transparent Background
animator = TextAnimator(
    **common_params,
)
animator.speed=60
animator.opacity=0.7
animator.color = (255, 0, 255)  # Magenta
animator.apply()
show_animation(animator, window_name="Transparent Background", num_frames=250)


# 22. Pausing the animation
animator = TextAnimator(
    **common_params,
)
animator.color = (255, 0, 255)
animator.speed = 300
animator.apply()
for i in range(800):
    if i in [100, 300, 500]:  # Pause at frame 100
        animator.pause()
    elif i in [200, 400, 600]:  # Resume at frame 200
        animator.resume()

    frame = animator.generate()
    if frame is not None:
        cv2.imshow("Pausing Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()
