import sys
import cv2
import screeninfo
import math
import threading
import asyncio
import websockets
import json
from camera import *
from virtual_objects import Vector2D
import itertools

class Tag:
    def __init__(self, id, raw_tag):
        self.id = id
        self.raw_tag = raw_tag
        self.corners = raw_tag.tolist()[0]

        # Individual corners (e.g. tl = top left corner in relation to the tag, not the camera)
        self.tl = Vector2D(int(self.corners[0][0]), int(self.corners[0][1])) # Top left
        self.tr = Vector2D(int(self.corners[1][0]), int(self.corners[1][1])) # Top right
        self.br = Vector2D(int(self.corners[2][0]), int(self.corners[2][1])) # Bottom right
        self.bl = Vector2D(int(self.corners[3][0]), int(self.corners[3][1])) # Bottom left

        # Calculate centre of the tag
        self.centre = Vector2D(int((self.tl.x + self.tr.x + self.br.x + self.bl.x) / 4),
                               int((self.tl.y + self.tr.y + self.br.y + self.bl.y) / 4))

        # Calculate centre of top of tag
        self.front = Vector2D(int((self.tl.x + self.tr.x) / 2),
                              int((self.tl.y + self.tr.y) / 2))


class Tracker(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.camera = Camera()

    def run(self):
        while True:        
            image = self.camera.get_frame()
            
            aruco_dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_100)
            aruco_parameters = cv2.aruco.DetectorParameters_create()

            (raw_tags, tag_ids, rejected) = cv2.aruco.detectMarkers(image, aruco_dictionary, parameters=aruco_parameters)

            # self.robot_ids = [] # Clear list every time in case robots have disappeared

            # if tag_ids is not None and len(tag_ids.tolist()) > 0:
            #     self.robot_ids = tag_ids.tolist()

            if tag_ids is not None and len(tag_ids.tolist()) > 0:

                tag_ids = list(itertools.chain(*tag_ids))
                tags = []

                for id, tag in zip(tag_ids, raw_tags):
                    tags.append(Tag(id, tag))
            
                for tag in tags:
                    print(tag.id, tag.centre)

                    red = (0, 0, 255)
                    green = (0, 255, 0)
                    magenta = (255, 0, 255)

                    # Draw border of tag
                    cv2.line(image, (tag.tl.x, tag.tl.y), (tag.tr.x, tag.tr.y), green, 1)
                    cv2.line(image, (tag.tr.x, tag.tr.y), (tag.br.x, tag.br.y), green, 1)
                    cv2.line(image, (tag.br.x, tag.br.y), (tag.bl.x, tag.bl.y), green, 1)
                    cv2.line(image, (tag.bl.x, tag.bl.y), (tag.tl.x, tag.tl.y), green, 1)
                    
                    # Draw circle on centre point
                    cv2.circle(image, (tag.centre.x, tag.centre.y), 5, red, -1)

                    # Draw line from centre point to front of tag
                    cv2.line(image, (tag.centre.x, tag.centre.y), (tag.front.x, tag.front.y), red, 2)

                    # Draw tag ID
                    text = str(tag.id)
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 1
                    thickness = 2
                    textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    position = (int(tag.centre.x - textsize[0]/2), int(tag.centre.y + textsize[1]/2))
                    cv2.putText(image, text, position, font, font_scale, green, thickness, cv2.LINE_AA)

            window_name = 'SwarmHack'

            # screen = screeninfo.get_monitors()[0]
            # width, height = screen.width, screen.height
            # image = cv2.resize(image, (width, height))
            # cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
            # cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

            cv2.imshow(window_name, image)

            # TODO: Fix quitting with Q (necessary for fullscreen mode)
            if cv2.waitKey(1) == ord('q'):
                sys.exit()

async def handler(websocket):
    async for packet in websocket:
        message = json.loads(packet)
        
        # Process any requests received
        reply = {}
        send_reply = False

        if "check_awake" in message:
            reply["awake"] = True
            send_reply = True

        if "get_ids" in message:
            reply["ids"] = cam.robot_ids
            send_reply = True

        # Send reply, if requested
        if send_reply:
            await websocket.send(json.dumps(reply))


# TODO: Handle Ctrl+C signals
if __name__ == "__main__":
    global tracker
    tracker = Tracker()
    tracker.start()
    
    start_server = websockets.serve(ws_handler=handler, host=None, port=6000)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server)
    loop.run_forever()
