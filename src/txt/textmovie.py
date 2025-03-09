import cv2
import numpy as np
from moviepy.editor import *
from moviepy.video.tools.segmenting import findObjects

class TextMovie:
    def __init__(self,
                 text="WLEDVideoSync",
                 color='red',
                 font_path=r"C:\Windows\Fonts\JOKERMAN.TTF",
                 fontsize=55,
                 screensize=(1024, 460),
                 fps=24):
        self.text = text
        self.color = color
        self.fps = fps
        self.font_path = font_path
        self.fontsize = fontsize
        self.screensize = screensize
        self.rotMatrix = lambda a: np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])
        self.txtClip = TextClip(self.text, color=self.color, font=self.font_path, fontsize=self.fontsize)
        self.initial_pos = 'center'  # Store the initial position
        self.cvc = CompositeVideoClip([self.txtClip.set_pos('center')], size=self.screensize)
        self.letters = findObjects(self.cvc)

    def create_animation(self, effects=None, durations=None):
        """Creates and concatenates animations based on provided effects and durations."""
        if durations is None:
            durations = [5, 5]
        if effects is None:
            effects = [self.effect1, self.effect2]
        if isinstance(durations, (int, float)):  # If a single duration is provided
            durations = [durations] * len(effects) # Use it for all effects

        clips = [CompositeVideoClip(self.move_letters(self.letters, effect), size=self.screensize).subclip(0, dur)
                 for effect, dur in zip(effects, durations)]
        final_clip = concatenate_videoclips(clips)
        final_clip.fps = self.fps
        return final_clip

    def effect1(self, screenpos, i, nletters):
        """Effect 1: Letters rotate and move inwards."""
        d = lambda t: 1.0 / (0.3 + t ** 8)
        a = i * np.pi / nletters
        v = self.rotMatrix(a).dot([-1, 0])
        if i % 2:
            v[1] = -v[1]
        return lambda t: screenpos + 400 * d(t) * self.rotMatrix(0.5 * d(t) * a).dot(v)

    def effect1_reverse(self, screenpos, i, nletters):
        """Effect 1 reversed: Letters move outwards and rotate."""
        d = lambda t: 1.0 / (0.3 + t ** 8)
        a = i * np.pi / nletters
        v = self.rotMatrix(-a).dot([1, 0])  # Reverse rotation and direction
        if i % 2:
            v[1] = -v[1]
        return lambda t: screenpos - 400 * d(t) * self.rotMatrix(-0.5 * d(t) * a).dot(v)  # Reverse rotation in matrix

    @staticmethod
    def effect2(screenpos, i, nletters):
        """Effect 2: Letters move upwards with a damping effect."""
        v = np.array([0, -1])
        d = lambda t: 1 if t < 0 else abs(np.sinc(t) / (1 + t ** 4))
        return lambda t: screenpos + v * 400 * d(t - 0.15 * i)

    @staticmethod
    def effect2_reverse(screenpos, i, nletters):
        """Effect 2 reversed: Letters move downwards with a damping effect."""
        v = np.array([0, 1])  # Reverse vertical direction
        d = lambda t: 1 if t < 0 else abs(np.sinc(t) / (1 + t ** 4))
        return lambda t: screenpos + v * 400 * d(t - 0.15 * i)

    def effect3(self, screenpos, i, nletters):
        """Effect 3: Letters fade out from the initial position."""
        d = lambda t: 1 - t  # Simple linear fade out

        # Calculate the initial position of the letters based on the text clip's position
        initial_letter_pos = np.array(self.txtClip.pos(0)) # 'center' is converted to actual coordinates

        return lambda t: screenpos + (screenpos - initial_letter_pos) * d(t)

    @staticmethod
    def effect4(screenpos, i, nletters):
        """Effect 4: Letters move in a wave-like pattern."""
        amplitude = 50  # Adjust the amplitude of the wave
        frequency = 2  # Adjust the frequency of the wave
        d = lambda t: amplitude * np.sin(2 * np.pi * frequency * t + i)
        return lambda t: screenpos + np.array([0, d(t)])

    def effect5(self, screenpos, i, nletters):
        """Effect 5: Letters explode outwards from the center."""
        center = np.array(self.screensize) / 2  # Calculate the center of the screen
        velocity = (screenpos - center) * 5  # Adjust the explosion speed
        return lambda t: center + velocity * t


    def set_text(self, new_text):
        """Updates the text and regenerates the text clip and letters."""
        self.text = new_text
        self.txtClip = TextClip(self.text, color=self.color, font=self.font_path, fontsize=self.fontsize)
        self.cvc = CompositeVideoClip([self.txtClip.set_pos(self.initial_pos)], size=self.screensize)
        self.letters = findObjects(self.cvc)

    @staticmethod
    def move_letters(letters, funcpos):
        """Applies a position function to each letter."""
        return [letter.set_pos(funcpos(letter.screenpos, i, len(letters))) for i, letter in enumerate(letters)]

    def show_in_real_time(self, effects=None, durations=None):
        """Display the animation frames in real-time using OpenCV with interactive controls."""
        final_clip = self.create_animation(effects=effects, durations=durations)

        # Debugging: Print out the number of subclips and final duration
        print(f"Final clip duration: {final_clip.duration} seconds")
        print(f"FPS: {final_clip.fps}")

        # Calculate the number of frames based on the duration and fps
        total_frames = int(final_clip.fps * final_clip.duration)
        print(f"Total frames to be extracted: {total_frames}")

        frames = []
        try:
            for t in range(total_frames):
                frame_time = t / final_clip.fps  # Convert frame index to time
                frame = final_clip.get_frame(frame_time)  # Extract the frame at that time

                frame = np.array(frame)

                # Ensure the frame is in the 0-255 range and cast to uint8 (8-bit format)
                frame = np.clip(frame * 255, 0, 255).astype(np.uint8)

                frames.append(frame)
        except Exception as e:
            print(f"Error while extracting frames: {e}")

        # Debugging: Check if frames were captured
        print(f"Total frames extracted: {len(frames)}")

        # Initialize variables for pause and skip
        pause = False
        skip_frame = False

        cv2.namedWindow("Text Animation", cv2.WINDOW_NORMAL)

        # Display each frame using OpenCV's imshow()
        for i, frame in enumerate(frames):
            # Convert frame from RGB to BGR (OpenCV expects BGR format)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Show the frame
            cv2.imshow("Text Animation", frame_bgr)

            # Wait for keypress for frame control
            key = cv2.waitKey(int(1000 / final_clip.fps)) & 0xFF

            if key == ord('q'):  # Press 'q' to quit
                break
            elif key == ord('p'):  # Press 'p' to pause/resume
                pause = not pause  # Toggle pause state
                print("Paused" if pause else "Resumed")
            elif key == ord('s'):  # Press 's' to skip a frame
                skip_frame = True
                print("Skipping to next frame...")

            # Pause logic: wait for the 'p' key to resume if paused
            while pause:
                key = cv2.waitKey(1) & 0xFF
                if key == ord('p'):  # Press 'p' again to resume
                    pause = False
                    print("Resumed")

            # Skip logic: if skip_frame is True, move to next frame
            if skip_frame:
                skip_frame = False  # Reset skip flag
                continue

        # Release resources when done
        cv2.destroyAllWindows()


if __name__ == "__main__":
    animator = TextMovie(text="WELCOME TO WLEDVIDEOSYNC")
    # Example usage with both effects
    # final_clip = animator.create_animation(effects=[animator.effect1, animator.effect2])
    # Example usage with only effect1
    animator.show_in_real_time(effects=[animator.effect2, animator.effect4, animator.effect5], durations=[5,5,2])
    my_final_clip = animator.create_animation(effects=[animator.effect2, animator.effect4, animator.effect5], durations=[5,5,2])
    # my_final_clip = animator.create_animation(durations=2)
    my_final_clip.ipython_display()

