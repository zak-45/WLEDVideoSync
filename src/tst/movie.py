import cv2

cv2.namedWindow("Video", cv2.WINDOW_GUI_EXPANDED)  # Create a resizable window
cap = cv2.VideoCapture(r"C:\Users\zak-4\PycharmProjects\WLEDVideoSync\media\Big_Buck_Bunny_360_10s_1MB.mp4")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    cv2.imshow("Video", frame)  # Show frame inside named window
    if cv2.waitKey(25) & 0xFF == ord("q"):  # Press 'q' to exit
        break

cap.release()
cv2.destroyAllWindows()
