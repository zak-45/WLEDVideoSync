import cv2
from src.txt.textanimator import TextAnimator
from src.utl.sharedlistclient import SharedListClient
from src.utl.cv2utils import CV2Utils as img_utils
import time

client = SharedListClient(sl_ip_address="127.0.0.1", sl_port=50001)
client.connect()
sl = client.attach_to_shared_list('Thread-2 (t_desktop_cast)')
sl_info = client.get_shared_list_info('Thread-2 (t_desktop_cast)')
print(sl_info)

# Example 16: Exploding text with pre-delay
animator = TextAnimator(
    text="WLED",
    width=1024,
    height=320,
    speed=0,  # No scrolling for this example
    alignment='center',
    direction='up', # up or down to stay fit
    color=(0, 0, 255),  # Blue text
    fps=15,
    font_path=r"‪C:\Windows\Fonts\8514oem.fon",  # Replace with your font path
    font_size=300,
    effect="explode",
    explode_speed=100,  # Adjust explosion speed as needed
    explode_pre_delay=2 # Delay before explosion in seconds
)

for _ in range(110):  # Adjust number of frames as needed
    frame = animator.generate()
    if frame is not None:
        frame_to_send = img_utils.resize_image(frame,32,32, keep_ratio=False)
        frame_to_send = img_utils.frame_add_one(frame_to_send)
        sl[0] = frame_to_send
        sl[1] = time.time()
        # print(frame_to_send)
        cv2.imshow("Exploding Text Animation", frame)
        cv2.waitKey(int(1000 / animator.fps))

cv2.destroyAllWindows()
animator.stop()

