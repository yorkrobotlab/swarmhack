import sys
import cv2
import screeninfo
import math

class coord:
    """Co-ordinate class to  make handling points easier"""
    
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __str__(self):
        return '(' + str(self.x) + ',' + str(self.y) + ')'

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Cannot open camera")
    exit()

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920) # Change to 4096 for 4k resolution
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080) # Change to 2160 for 4k resolution
cap.set(cv2.CAP_PROP_FPS, 30)

while True:
   
    ret, frame = cap.read()
   
    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break
       
    (tags, ids, rejected) = cv2.aruco.detectMarkers(frame, cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_100), parameters=cv2.aruco.DetectorParameters_create())

    cv2.aruco.drawDetectedMarkers(frame, tags, ids, borderColor = (0, 255, 0))
     
    print(ids)

    for tag in tags:
        corners = tag.tolist()[0]

        # Individual corners (e.g. tl = top left corner in relation to the tag, not the camera)
        tl = coord(corners[0][0], corners[0][1])
        tr = coord(corners[1][0], corners[1][1])
        br = coord(corners[2][0], corners[2][1])
        bl = coord(corners[3][0], corners[3][1])

        # Get centre of the tag
        cX = int((tl.x + tr.x + br.x + bl.x) / 4)
        cY = int((tl.y + tr.y + br.y + bl.y) / 4)

        # Draw circle on centre point
        cv2.circle(frame, (cX, cY), 5, (0, 0, 255), -1)

        # Get centre of top of tag
        tX = int((tl.x + tr.x) / 2)
        tY = int((tl.y + tr.y) / 2)

        # Draw line from centre point to front of robot (shows direction of movement)
        cv2.line(frame, (cX, cY), (tX, tY), (0, 0, 255), 2)

    window_name = 'SwarmHack'

    # screen = screeninfo.get_monitors()[0]
    # width, height = screen.width, screen.height
    # frame = cv2.resize(frame, (width, height))
    # cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    # cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    cv2.imshow(window_name, frame)

    if cv2.waitKey(1) == ord('q'):
      sys.exit()
