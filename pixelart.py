import cv2
import numpy as np

# Input image
my_input = cv2.imread("C:\\Users\\zak-4\\Pictures\\nikos.jpg")

# Get input size
height, width = my_input.shape[:2]

# Desired "pixelated" size
w, h = (100, 200)

# Resize input to "pixelated" size
temp = cv2.resize(my_input, (w, h), interpolation=cv2.INTER_LINEAR)

# Initialize output image
output = cv2.resize(temp, (width, height), interpolation=cv2.INTER_NEAREST)

cv2.imshow('Input', my_input)
cv2.imshow('Output', output)

cv2.waitKey(0)
