# importing Numpy
import numpy as np

# importing moviepy module
from moviepy.editor import *
from moviepy.video.tools.segmenting import findObjects

# screen size
screensize = (720, 460)

# creating a text clip of color green, font is Arial and size is 80
txtClip = TextClip('WLEDVIDEOSYNC', color='lightgreen', font="Arial",
                   kerning=5, fontsize=60)

# creating a composite video of given size
cvc = CompositeVideoClip([txtClip.set_pos('center')],
                         size=screensize)

# helper function
rotMatrix = lambda a: np.array([[np.cos(a), np.sin(a)],
                                [-np.sin(a), np.cos(a)]])


# creating a effect 1 method
def effect1(screenpos, i, nletters):
    # damping
    d = lambda t: 1.0 / (0.3 + t ** 8)
    # angle of the movement
    a = i * np.pi / nletters

    # using helper function
    v = rotMatrix(a).dot([-1, 0])

    if i % 2: v[1] = -v[1]

    # returning the function
    return lambda t: screenpos + 400 * d(t) * rotMatrix(0.5 * d(t) * a).dot(v)


# method for effect 2
def effect2(screenpos, i, nletters):
    # numpy array
    v = np.array([0, -1])

    d = lambda t: 1 if t < 0 else abs(np.sinc(t) / (1 + t ** 4))

    # returning the function
    return lambda t: screenpos + v * 400 * d(t - 0.15 * i)


# a list of ImageClips
letters = findObjects(cvc)


# method to move letters
def moveLetters(letters, funcpos):
    return [letter.set_pos(funcpos(letter.screenpos, i, len(letters)))
            for i, letter in enumerate(letters)]


# adding clips with specific effect
clips = [CompositeVideoClip(moveLetters(letters, funcpos),
                            size=screensize).subclip(0, 5)
         for funcpos in [effect1, effect2]]

# comping all the clips
final_clip = concatenate_videoclips(clips)

# setting fps of the final clip
final_clip.fps = 24

# showing video clip
final_clip.preview()
final_clip.ipython_display(t=8)
