import cv2
import sys

class Camera:
	
    def __init__(self):

        self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

        if not self.cap.isOpened():
            print("Cannot open camera")
            sys.exit(0)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        # https://answers.opencv.org/question/211355/how-to-disable-autofocus-of-a-webcam-on-windows-10/
        # https://stackoverflow.com/questions/19813276/manually-focus-webcam-from-opencv
        focus = 0 # min: 0, max: 255, increment:5
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        self.cap.set(cv2.CAP_PROP_FOCUS, focus)

    def get_frame(self):
        ret, frame = self.cap.read()
        return frame