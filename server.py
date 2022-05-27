import sys
import cv2
import screeninfo

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
       
    (tags, ids, rejected) = cv2.aruco.detectMarkers(frame, cv2.aruco.Dictionary_get(cv2.aruco.DICT_5X5_50), parameters=cv2.aruco.DetectorParameters_create())

    cv2.aruco.drawDetectedMarkers(frame, tags, borderColor = (0, 255, 0))
     
    print(ids)

    window_name = 'SwarmHack'

    # screen = screeninfo.get_monitors()[0]
    # width, height = screen.width, screen.height
    # frame = cv2.resize(frame, (width, height))
    # cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    # cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    cv2.imshow(window_name, frame)

    if cv2.waitKey(1) == ord('q'):
      sys.exit()
