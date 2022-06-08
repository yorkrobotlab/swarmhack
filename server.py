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

red = (0, 0, 255)
green = (0, 255, 0)
magenta = (255, 0, 255)
cyan = (255, 255, 0)

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

class Robot:
    def __init__(self, tag):
        self.tag = tag
        self.id = tag.id
        self.position = tag.centre


class Tracker(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.camera = Camera()
        self.calibrated = False
        self.num_corner_tags = 0
        self.min_x = 0
        self.min_y = 0
        self.max_x = 0
        self.max_y = 0
        self.robots = {}

    def run(self):
        while True:        
            image = self.camera.get_frame()
            overlay = image.copy()
            
            aruco_dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_100)
            aruco_parameters = cv2.aruco.DetectorParameters_create()

            (raw_tags, tag_ids, rejected) = cv2.aruco.detectMarkers(image, aruco_dictionary, parameters=aruco_parameters)

            self.robots = {} # Clear dictionary every frame in case robots have disappeared

            # Check whether any tags were detected in this camera frame
            if tag_ids is not None and len(tag_ids.tolist()) > 0:

                tag_ids = list(itertools.chain(*tag_ids))

                # Process raw ArUco output
                for id, raw_tag in zip(tag_ids, raw_tags):

                    tag = Tag(id, raw_tag)

                    if self.calibrated:
                        if tag.id != 0: # Reserved tag ID for corners
                            self.robots[id] = Robot(tag)
                    else: # Only calibrate the first time two corner tags are detected
                       
                        if tag.id == 0: # Reserved tag ID for corners

                            if self.num_corner_tags == 0: # Record the first corner tag detected
                                self.min_x = tag.centre.x
                                self.max_x = tag.centre.x
                                self.min_y = tag.centre.y
                                self.max_y = tag.centre.y
                            else: # Set min/max boundaries of arena based on second corner tag detected

                                if tag.centre.x < self.min_x:
                                    self.min_x = tag.centre.x
                                if tag.centre.x > self.max_x:
                                    self.max_x = tag.centre.x
                                if tag.centre.y < self.min_y:
                                    self.min_y = tag.centre.y
                                if tag.centre.y > self.max_y:
                                    self.max_y = tag.centre.y

                                corner_distance_metres = 1.78 # Euclidean distance between corner tags in metres
                                corner_distance_pixels = math.dist([self.min_x, self.min_y], [self.max_x, self.max_y]) # Euclidean distance between corner tags in pixels
                                scale_factor = corner_distance_pixels / corner_distance_metres
                                sensor_range = int(0.3 * scale_factor) # 30cm sensing radius

                                self.calibrated = True

                            self.num_corner_tags = self.num_corner_tags + 1

                if self.calibrated:

                    # Draw boundary of virtual environment based on corner tag positions
                    cv2.rectangle(image, (self.min_x, self.min_y), (self.max_x, self.max_y), green, 5, lineType=cv2.LINE_AA)
            
                    # Rendering
                    for id, robot in self.robots.items():
                        tag = robot.tag

                        # Draw border of tag
                        cv2.line(image, (tag.tl.x, tag.tl.y), (tag.tr.x, tag.tr.y), green, 1, lineType=cv2.LINE_AA)
                        cv2.line(image, (tag.tr.x, tag.tr.y), (tag.br.x, tag.br.y), green, 1, lineType=cv2.LINE_AA)
                        cv2.line(image, (tag.br.x, tag.br.y), (tag.bl.x, tag.bl.y), green, 1, lineType=cv2.LINE_AA)
                        cv2.line(image, (tag.bl.x, tag.bl.y), (tag.tl.x, tag.tl.y), green, 1, lineType=cv2.LINE_AA)
                        
                        # Draw circle on centre point
                        cv2.circle(image, (tag.centre.x, tag.centre.y), 5, red, -1, lineType=cv2.LINE_AA)

                        # Draw line from centre point to front of tag
                        cv2.line(image, (tag.centre.x, tag.centre.y), (tag.front.x, tag.front.y), red, 2, lineType=cv2.LINE_AA)

                        # Draw tag ID
                        text = str(tag.id)
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 1
                        thickness = 2
                        textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
                        position = (int(tag.centre.x - textsize[0]/2), int(tag.centre.y + textsize[1]/2))
                        cv2.putText(image, text, position, font, font_scale, green, thickness, cv2.LINE_AA)

                        # Draw robot's sensor range
                        cv2.circle(overlay, (tag.centre.x, tag.centre.y), sensor_range, magenta, -1, lineType=cv2.LINE_AA)

                        # Draw lines between robots if they are within sensor range
                        for id, other_robot in self.robots.items():
                            other_tag = other_robot.tag
                            if tag.id != other_tag.id:
                                if math.dist([tag.centre.x, tag.centre.y], [other_tag.centre.x, other_tag.centre.y]) < sensor_range:
                                    cv2.line(image, (tag.centre.x, tag.centre.y), (other_tag.centre.x, other_tag.centre.y), cyan, 2, lineType=cv2.LINE_AA)        

                    # Transparency for overlaid augments
                    alpha = 0.3
                    image = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)

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
            reply["ids"] = tracker.robots.keys()
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
