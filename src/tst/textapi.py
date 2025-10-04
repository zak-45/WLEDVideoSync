from fastapi import FastAPI
from pydantic import BaseModel
from src.txt.textanimator import TextAnimator
from typing import Optional, Tuple

# FastAPI integration
app = FastAPI()
animator = TextAnimator(
    text="Hello, FastAPI!",
    width=800,
    height=200,
    speed=50,
    direction="left",
    color=(255, 255, 255),
    fps=30
)

class TextUpdateRequest(BaseModel):
    text: str

class AnimatorConfigRequest(BaseModel):
    text: str
    width: int
    height: int
    speed: float
    direction: str
    color: Tuple[int, int, int]
    fps: int
    font_path: Optional[str] = None
    font_size: Optional[int] = None
    bg_color: Optional[Tuple[int, int, int]] = None
    opacity: float = 1.0
    effect: Optional[str] = None
    alignment: str = "left"
    shadow: bool = False
    shadow_color: Tuple[int, int, int] = (0, 0, 0)
    shadow_offset: Tuple[int, int] = (2, 2)


@app.post("/update-text")
def update_text(request: TextUpdateRequest):
    """Update the text of the animator in real-time."""
    animator.text = request.text
    animator.text_image = animator.create_text_image()
    return {"status": "Text updated successfully."}

@app.post("/pause")
def pause_animation():
    """Pause the animation."""
    animator.pause()
    return {"status": "Animation paused."}

@app.post("/resume")
def resume_animation():
    """Resume the animation."""
    animator.resume()
    return {"status": "Animation resumed."}

@app.post("/create-scroll-blink")
def create_scroll_blink():
    """Create a basic scroll animation with a blink effect for 'WLEDVideoSync'."""
    animator.text = "WLEDVideoSync"
    animator.speed = 100  # Adjust speed for scrolling effect
    animator.effect = "blink"  # Set blink effect
    animator.text_image = animator.create_text_image()
    return {"status": "Scroll with blink effect created.", "text": animator.text}


@app.post("/send-frame/{frame_queue}")
def send_frame(frame_queue=None):
    """Send the current animation frame to the queue."""
    animator.send_frame_to_queue(frame_queue)
    return {"status": "Frame sent to queue."}


@app.post("/configure-animator")
def configure_animator(request: AnimatorConfigRequest):
    """Configure the TextAnimator with all available parameters."""
    global animator
    animator = TextAnimator(
        text=request.text,
        width=request.width,
        height=request.height,
        speed=request.speed,
        direction=request.direction,
        color=request.color,
        fps=request.fps,
        font_path=request.font_path,
        font_size=request.font_size,
        bg_color=request.bg_color,
        opacity=request.opacity,
        effect=request.effect,
        vertical_align=request.alignment,
        shadow=request.shadow,
        shadow_color=request.shadow_color,
        shadow_offset=request.shadow_offset
    )
    return {"status": "Animator configured successfully.", "text": animator.text}

@app.get("/status")
def get_status():
    """Get the current status of the animator."""
    status = "paused" if animator.paused else "running"
    return {"status": status, "current_text": animator.text}
