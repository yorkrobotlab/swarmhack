#!/usr/bin/env python3

from pynput import keyboard
import math
import threading
import asyncio
import websockets
import json
from camera import *
from vector2d import Vector2D
import itertools
import random
import angles
import time
from ballgame_roles import *

red = (0, 0, 255)
green = (0, 255, 0)
blue = (255, 0, 0)
purple = (128, 0, 128)
magenta = (255, 0, 255)
cyan = (255, 255, 0)
yellow = (50, 255, 255)
black = (0, 0, 0)
white = (255, 255, 255)
grey = (100, 100, 100)

PUCK_ID = 1
GAME_TIME = 5 * 60
# random.seed(1)

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

        # Calculate orientation of tag
        self.forward = math.atan2(self.front.y - self.centre.y, self.front.x - self.centre.x) # Forward vector
        self.angle = math.degrees(self.forward) # Angle between forward vector and x-axis

class Robot:
    def __init__(self, tag, position):
        self.tag = tag
        self.id = tag.id
        self.position = position
        self.orientation = tag.angle
        self.sensor_range = 0.3 # 30cm sensing radius
        self.neighbours = {}

        self.out_of_bounds = False
        self.distance = 0
        self.ball_dist = None
        self.team = Team.UNASSIGNED
        self.role = Role.NOMAD
        self.ball = None

class Ball:
    def __init__(self, position, tag):
        self.position = position
        self.radius = 30
        self.tag = tag
        self.id = PUCK_ID

class Zone:
    """
    Creates a zone from x value and width of the zone

    De Jure robots  -- Robots that rightfully belong to the zone
    De Facto robots -- Robots that are currently inside the zone

    """
    def __init__(self, x, y, width, height):
        self.de_jure_robots = []
        self.rule_breakers = []

        self.x1 = x
        self.x2 = x + width

        self.y1 = y
        self.y2 = y + height

        self.width = width
        self.height = height

        self.centre_x = self.x1 + self.width / 2
        self.centre_y = self.y1 + self.height / 2

        self.randomise_starting_positions()

    def randomise_starting_positions(self):
        self.possible_starting_positions = []

        for position in range(4):
            random_x = random.uniform(self.centre_x - self.width / 4, self.centre_x + self.width / 4)
            random_y = random.uniform(self.centre_y - self.width / 4, self.centre_y + self.width / 4)
            self.possible_starting_positions.append((random_x, random_y))

        self.starting_position = self.possible_starting_positions[random.randint(0, 3)]

        return self.starting_position


    def addDeJure(self, robot):
        self.de_jure_robots.append(robot)

    def contains(self, ball):
        ball_x = ball.tag.centre.x
        ball_y = ball.tag.centre.y
        if (ball_x - ball.radius) > self.x1 and \
                (ball_x + ball.radius) < self.x2 and \
                (ball_y + ball.radius) < self.y2 and \
                (ball_y - ball.radius) > self.y1:
            return True
        return False

    def buildDeJure(self, robots, red_role):
        for id, robot in robots.items():
            if self.x1 <= robot.tag.centre.x <= self.x2:
                self.de_jure_robots.append(id)
                if (robot.team == Team.RED):
                    robot.role = red_role
                elif (robot.team == Team.BLUE):
                    if (red_role == Role.STRIKER):
                        robot.role = Role.DEFENDER
                    elif (red_role == Role.DEFENDER):
                        robot.role = Role.STRIKER
                    else:
                        robot.role = Role.MID_FIELD
                else:
                    robot.role = Role.NOMAD
                robots[id] = robot
        return robots
    def getZone(self):
        return (self.x1, self.x2)

    def checkRobots(self, robots):
        self.rule_breakers = []

        for id, robot in robots.items():
            if id in self.de_jure_robots:

                if self.x1 > robot.tag.centre.x or robot.tag.centre.x > self.x2:

                    self.rule_breakers.append(id)

        return robots

    def assignTeam(self, robots, team):

        for id, robot in robots.items():
            if self.x1 <= robot.tag.centre.x <= self.x2:
                robot.team = team
        return robots

class Goal:
    def __init__(self, x, y, width, height):
        self.x1 = x
        self.y1 = y

        self.x2 = x + width
        self.y2 = y + height

        self.score = 0

        self.centre = Vector2D((self.x2 - self.x1)/2 + self.x1, (self.y2 - self.y1)/2 + self.y1)

    def check(self, ball):
        ball_x = ball.tag.centre.x
        ball_y = ball.tag.centre.y

        if (ball_x - ball.radius) > self.x1 and \
                (ball_x + ball.radius) < self.x2 and \
                (ball_y + ball.radius) < self.y2 and \
                (ball_y - ball.radius) > self.y1:
            self.score += 1
            return True
        return False

class SensorReading:
    def __init__(self, range, bearing, orientation=0, workers=0):
        self.range = range
        self.bearing = bearing
        self.orientation = orientation
        self.workers = workers

class TimerStatus(Enum):
    STOPPED = 0
    STARTED = 1
    PAUSED = 2
    COMPLETE = 3

class Timer:
    def __init__(self, time_limit):
        self.time_limit = time_limit
        self.time_left = time_limit
        self.status = TimerStatus.STOPPED
        self.elapsed_time = 0
        self.start_time = 0
    def start(self):
        self.start_time = time.time()
        self.elapsed_time = 0
        self.status = TimerStatus.STARTED

    def pause(self):
        self.elapsed_time = time.time() - self.start_time
        self.status = TimerStatus.PAUSED

    def unpause(self):
        self.status = TimerStatus.STARTED
        self.time_limit = self.time_limit - self.elapsed_time
        self.start_time = time.time()

    def update(self):
        if self.status == TimerStatus.STARTED:
            self.elapsed_time = time.time() - self.start_time
            self.time_left = self.time_limit - self.elapsed_time
            if self.time_left <= 0:
                self.status = TimerStatus.COMPLETE
                self.time_left = 0

    def getColor(self):
        if self.status == TimerStatus.STARTED:
            if self.time_left <= 31:
                return yellow
            else:
                return white
        elif self.status == TimerStatus.PAUSED:
            return grey
        elif self.status == TimerStatus.COMPLETE:
            return red
        else:
            return red

    def getString(self):

        time_string = ""
        seconds = int(self.time_left) % 60
        minutes = int(self.time_left) // 60

        seconds = str(seconds)

        if len(seconds) == 1:
            seconds = "0" + seconds
        time_string = str(minutes) + ":" + seconds
        return time_string

class Tracker(threading.Thread):


    def __init__(self):

        threading.Thread.__init__(self)
        self.camera = Camera()
        self.calibrated = False
        self.num_corner_tags = 0
        self.min_x = 0 # In pixels
        self.min_y = 0 # In pixels
        self.max_x = 0 # In pixels
        self.max_y = 0 # In pixels
        self.centre = Vector2D(0, 0) # In metres
        self.corner_distance_metres = 2.06 # Euclidean distance between corner tags in metres
        self.corner_distance_pixels = 0
        self.scale_factor = 0
        self.robots = {}

        self.red_goal = None
        self.blue_goal = None
        self.ball = None
        self.zones = []
        self.gameState = 0
        self.timer = Timer(GAME_TIME)
        self.roboteams = {}



        listener = keyboard.Listener(
            on_press=self.on_press)
        listener.start()

    def on_press(self, key):
        try:
            if key.char == 'p':
                if self.timer.status == TimerStatus.PAUSED:
                    self.timer.unpause()
                else:
                    self.timer.pause()
            if key.char == 'l':

                for zone in self.zones:
                    print(zone.rule_breakers, zone.x1, zone.x2)
                    print(zone.de_jure_robots)
                    for id, robot in self.robots.items():
                        print(id, robot.role)
            if key.char == 'b':
                newzones = []
                zone_role = 0
                for zone in self.zones:
                    zone.de_jure_robots = []
                    self.robots = zone.buildDeJure(self.robots, Role(zone_role))
                    zone_role += 1
                    newzones.append(zone)
                self.zones = newzones
            if key.char == 't':
                self.robots = self.zones[0].assignTeam(self.robots, Team.RED)
                self.robots = self.zones[len(self.zones)-1].assignTeam(self.robots, Team.BLUE)

            if key.char == 'r':
                self.timer = Timer(GAME_TIME)
                # self.timer.start()
                # self.timer.pause()
                self.red_goal.score = 0
                self.blue_goal.score = 0
                self.gameState = 1
                self.reset_zone = Zone((self.max_x - self.min_x) / 2 - 75 + self.min_x,
                                       (self.max_y - self.min_y) / 2 + self.min_y - 75, 150, 150)
                self.robots = {}
                for zone in self.zones:
                    zone.de_jure_robots = []

            if key.char == 'x':
                for zone in self.zones:
                    zone.starting_position = zone.randomise_starting_positions()

            if key.char == '[':
                self.blue_goal.score -= 1
            elif key.char == ']':
                self.blue_goal.score += 1
            elif key.char == ',':
                self.red_goal.score -= 1
            elif key.char == '.':
                self.red_goal.score += 1
        except AttributeError as e:
            print('special key {0} pressed'.format(
                key))
            print(e)
    """
    processes raw tags and updates self.robots to contain a dictionary of all visible robots and their IDs
    
    tag_ids
    raw_tags -- 
    List reserved_tags -- List of tags the process should skip (E.g. The corner tags and the ball)
    """
    def processArUco(self, tag_ids, raw_tags):
        for id, raw_tag in zip(tag_ids, raw_tags):

            tag = Tag(id, raw_tag)

            if self.calibrated:
                if (tag.id == self.ball.id):
                    position = Vector2D(tag.centre.x / self.scale_factor,
                                        tag.centre.y / self.scale_factor)
                    self.ball.position = position
                    self.ball.tag = tag

                if (tag.id not in [0, self.ball.id]):  # Reserved tag ID for corners and for ball
                    position = Vector2D(tag.centre.x / self.scale_factor,
                                        tag.centre.y / self.scale_factor)  # Convert pixel coordinates to metres
                    if (tag.id in self.robots.keys()):
                        self.robots[tag.id].position = position
                        self.robots[id].orientation = tag.angle
                        self.robots[id].tag = tag
                    else:
                        self.robots[id] = Robot(tag, position)

            else:  # Only calibrate the first time two corner tags are detected
                self.calibrate(tag)
    """
    Defines an amount of uniformly sized, uniformly spaced Zones equal to the zone_amount
    
    zone_amount -- amount of zones to be defined
    offset      -- how far the zones overlap (Default : 150)
    
    """
    def defineZones(self, zone_amount, offset=150):
        max_width = self.max_x - self.min_x
        zone_width = max_width / zone_amount

        x = self.min_x + offset/2
        for zone in range(zone_amount):
            z = Zone(x-offset, self.min_y, zone_width+offset, self.max_y - self.min_y)
            if (z.x1 < self.min_x):
                z.x1 = self.min_x
            elif (z.x2 > self.max_x):
                z.x2 = self.max_x
            self.zones.append(z)
            x += zone_width

    """
    Draws the Zones on to the image-display
    
    image -- camera image for the zones to be drawn on top of.
    """
    def drawZones(self, image):
        colors = [red, grey, blue]
        for zone_index in range(len(self.zones)):
            zone = self.zones[zone_index]
            cv2.rectangle(image, (int(zone.x1), zone.y1), (int(zone.x2), zone.y2), colors[zone_index % len(colors)], 3, lineType=cv2.LINE_AA)

            if self.timer.status == TimerStatus.STOPPED:
                cv2.circle(image, (int(zone.starting_position[0]), int(zone.starting_position[1])), 25, red, -1, lineType=cv2.LINE_AA)
                cv2.circle(image, (int(self.min_x + self.max_x - zone.starting_position[0]), int(self.min_y + self.max_y - zone.starting_position[1])), 25, blue, -1, lineType=cv2.LINE_AA)


    def defineGoals(self, goal_width, goal_height):
        x = self.min_x
        y = ((self.max_y - self.min_y) - goal_height) / 2 + self.min_y
        self.red_goal = Goal(int(x), int(y), goal_width, goal_height)

        x = self.max_x - goal_width
        self.blue_goal = Goal(int(x), int(y), goal_width, goal_height)

    def drawGoals(self, image):
        cv2.rectangle(image, (self.red_goal.x1, self.red_goal.y1), (self.red_goal.x2, self.red_goal.y2), red,
                      3, lineType=cv2.LINE_AA)
        cv2.rectangle(image, (self.blue_goal.x1, self.blue_goal.y1), (self.blue_goal.x2, self.blue_goal.y2), blue,
                      3, lineType=cv2.LINE_AA)


    """
    Calibrates the play area ready for a match
    
    tag -- a tag of ID=0
    """
    def calibrate(self, tag):
        if tag.id == PUCK_ID:
            self.ball = Ball(Vector2D(0, 0), tag)

        if tag.id == 0:  # Reserved tag ID for corners

            if self.num_corner_tags == 0:  # Record the first corner tag detected
                self.min_x = tag.centre.x
                self.max_x = tag.centre.x
                self.min_y = tag.centre.y
                self.max_y = tag.centre.y
            else:  # Set min/max boundaries of arena based on second corner tag detected

                if tag.centre.x < self.min_x:
                    self.min_x = tag.centre.x
                if tag.centre.x > self.max_x:
                    self.max_x = tag.centre.x
                if tag.centre.y < self.min_y:
                    self.min_y = tag.centre.y
                if tag.centre.y > self.max_y:
                    self.max_y = tag.centre.y

                self.corner_distance_pixels = math.dist([self.min_x, self.min_y], [self.max_x,
                                                                                   self.max_y])  # Euclidean distance between corner tags in pixels
                self.scale_factor = self.corner_distance_pixels / self.corner_distance_metres
                x = ((self.max_x - self.min_x) / 2) / self.scale_factor  # Convert to metres
                y = ((self.max_y - self.min_y) / 2) / self.scale_factor  # Convert to metres
                self.centre = Vector2D(x, y)

                self.defineZones(3)
                self.defineGoals(int((self.max_x - self.min_x) / 7), int((self.max_y - self.min_y) / 2))


                self.calibrated = True


            self.num_corner_tags = self.num_corner_tags + 1

    """
        Backend processing for the robots.

        Currently: Builds a map of neighbouring robots.
    """

    def processRobots(self):
        for id, robot in self.robots.items():

            for other_id, other_robot in self.robots.items():

                if id != other_id:  # Don't check this robot against itself

                    range = robot.position.distance_to(other_robot.position)

                    absolute_bearing = math.degrees(math.atan2(other_robot.position.y - robot.position.y,
                                                               other_robot.position.x - robot.position.x))
                    relative_bearing = absolute_bearing - robot.orientation
                    normalised_bearing = angles.normalize(relative_bearing, -180, 180)
                    robot.neighbours[other_id] = SensorReading(range, normalised_bearing, other_robot.orientation)

            range = robot.position.distance_to(self.ball.position)
            absolute_bearing = math.degrees(math.atan2(self.ball.position.y - robot.position.y,
                                                       self.ball.position.x - robot.position.x))
            relative_bearing = absolute_bearing - robot.orientation
            normalised_bearing = angles.normalize(relative_bearing, -180, 180)
            robot.ball = SensorReading(range, normalised_bearing)

            zone_roles = [Role.DEFENDER, Role.MID_FIELD, Role.STRIKER]
            for zone in range(len(self.zones)-1):
                if id in self.zones[zone].de_jure_robots and ((self.robots[id].team == Team.RED and self.robots[id].role == zone_roles[zone]) or (self.robots[id].team == Team.BLUE and self.robots[id].role == zone_roles[len(zone_roles) - zone - 1])):
                    robot.distance = (robot.tag.centre.x - self.zones[zone].x1) / self.zones[zone].width
                    if self.robots[id].team == Team.BLUE:
                        robot.distance = 1 - robot.distance
                    break
            else:
                robot.distance = 0  # this is not special its just here to hopefully avoid future errors


            range = robot.position.distance_to(self.red_goal.centre / self.scale_factor)
            absolute_bearing = math.degrees(math.atan2((self.red_goal.centre.y / self.scale_factor) - robot.position.y,
                                                       (self.red_goal.centre.x / self.scale_factor) - robot.position.x))
            relative_bearing = absolute_bearing - robot.orientation
            normalised_bearing = angles.normalize(relative_bearing, -180, 180)
            goal1 = SensorReading(range, normalised_bearing)

            range = robot.position.distance_to(self.blue_goal.centre / self.scale_factor)
            absolute_bearing = math.degrees(math.atan2((self.blue_goal.centre.y / self.scale_factor) - robot.position.y,
                                                       (self.blue_goal.centre.x / self.scale_factor) - robot.position.x))
            relative_bearing = absolute_bearing - robot.orientation
            normalised_bearing = angles.normalize(relative_bearing, -180, 180)
            goal2 = SensorReading(range, normalised_bearing)

            if robot.team == Team.BLUE:
                robot.strike_goal = goal1
                robot.defend_goal = goal2
            else:
                robot.strike_goal = goal2
                robot.defend_goal = goal1



    """
    Draws bounding box of the arena.
    
    image -- The camera image for the box to be drawn on to. 
    """
    def drawBoundingBox(self, image):
        cv2.rectangle(image, (self.min_x, self.min_y), (self.max_x, self.max_y), green, 1, lineType=cv2.LINE_AA)

    """
    Responsible for drawing any UI element associated with the robots.
    
    image -- The camera image for the robots to be drawn onto
    """
    def drawRobots(self, image):
        for id, robot in self.robots.items():

            # Draw tag
            tag = robot.tag

            # Draw border of tag
            cv2.line(image, (tag.tl.x, tag.tl.y), (tag.tr.x, tag.tr.y), green, 1, lineType=cv2.LINE_AA)
            cv2.line(image, (tag.tr.x, tag.tr.y), (tag.br.x, tag.br.y), green, 1, lineType=cv2.LINE_AA)
            cv2.line(image, (tag.br.x, tag.br.y), (tag.bl.x, tag.bl.y), green, 1, lineType=cv2.LINE_AA)
            cv2.line(image, (tag.bl.x, tag.bl.y), (tag.tl.x, tag.tl.y), green, 1, lineType=cv2.LINE_AA)

            # Draw circle on centre point
            cv2.circle(image, (tag.centre.x, tag.centre.y), 5, red, -1, lineType=cv2.LINE_AA)

            tag = robot.tag

            # Draw line from centre point to front of tag
            forward_point = ((tag.front - tag.centre) * 2) + tag.centre


            # Draw tag ID

            for zone in self.zones:
                if id in zone.rule_breakers:
                    text2 = "X"
                    break
            else:
                text2 = ""

            text = robot.role.name
            # text3 = str(round(robot.distance, 2))
            text3 = str(robot.tag.id)

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.5
            thickness = 4
            textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
            position = (int(tag.centre.x - textsize[0] / 2), int(tag.centre.y + textsize[1] / 2 - 3))
            position2 = (int(tag.centre.x - textsize[0] / 2), int(tag.centre.y + textsize[1] / 2 - 2 * textsize[1]))
            cv2.putText(image, text2, position, font, font_scale * 3, red, thickness * 4, cv2.LINE_AA)
            if robot.team == Team.RED:
                teamcolor = red
            elif robot.team == Team.BLUE:
                teamcolor = blue
            else:
                teamcolor = magenta

            cv2.putText(image, text, position, font, font_scale, white, thickness * 3, cv2.LINE_AA)
            cv2.putText(image, text, position, font, font_scale, teamcolor, thickness, cv2.LINE_AA)

            cv2.putText(image, text3, position2, font, font_scale, white, thickness * 3, cv2.LINE_AA)
            cv2.putText(image, text3, position2, font, font_scale, teamcolor, thickness, cv2.LINE_AA)
            cv2.line(image, (tag.centre.x, tag.centre.y), (forward_point.x, forward_point.y), black, 10,
                     lineType=cv2.LINE_AA)
            cv2.line(image, (tag.centre.x, tag.centre.y), (forward_point.x, forward_point.y), green, 3,
                     lineType=cv2.LINE_AA)


    def drawBall(self, image):
        cv2.circle(image, (self.ball.tag.centre.x, self.ball.tag.centre.y), 5, red, -1, lineType=cv2.LINE_AA)

        text = "BALL"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.5
        thickness = 4
        textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
        position = (int(self.ball.tag.centre.x - textsize[0] / 2), int(self.ball.tag.centre.y + textsize[1] / 2))

        cv2.putText(image, text, position, font, font_scale, white, thickness * 3, cv2.LINE_AA)
        cv2.putText(image, text, position, font, font_scale, green, thickness, cv2.LINE_AA)


    def processGame(self, image):
        newzones = []
        for zone in self.zones:
            zone.checkRobots(self.robots)
            newzones.append(zone)
        self.zones = newzones

        if self.timer.status != TimerStatus.PAUSED and self.timer.status != TimerStatus.COMPLETE:
            if self.blue_goal.check(self.ball) or self.red_goal.check(self.ball):
                self.timer.pause()
                self.gameState = 1
                self.reset_zone = Zone((self.max_x - self.min_x)/2 - 75 + self.min_x, (self.max_y - self.min_y)/2 + self.min_y - 75, 150, 150)
        if (self.timer.status == TimerStatus.PAUSED or self.timer.status == TimerStatus.STOPPED) and self.gameState == 1:
            cv2.rectangle(image, (int(self.reset_zone.x1), int(self.reset_zone.y1)),
                          (int(self.reset_zone.x2), int(self.reset_zone.y2)),
                          green, 2, lineType=cv2.LINE_AA)
            if self.reset_zone.contains(self.ball):
                self.timer.unpause()
                self.gameState = 0
        elif self.timer.status == TimerStatus.COMPLETE:
            if self.blue_goal.score > self.red_goal.score:
                # red wins
                text = "RED WINS"
                tcolor = red
            elif self.red_goal.score > self.blue_goal.score:
                # blue wins
                text = "BLUE WINS"
                tcolor = blue
            else:
                text = "DRAW"
                tcolor = yellow

            offset = 0
            for i in text:
                if i == "I":
                    offset += 21
                else:
                    offset += 63

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 2
            thickness = 5
            textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
            position = (960 - offset, 540)
            cv2.putText(image, text, position, font, font_scale * 3, tcolor, thickness * 3, cv2.LINE_AA)
            cv2.putText(image, text, position, font, font_scale * 3, black, thickness, cv2.LINE_AA)

    def run(self):
        while True:        
            image = self.camera.get_frame()
            overlay = image.copy()
            
            aruco_dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_100)
            aruco_parameters = cv2.aruco.DetectorParameters_create()

            (raw_tags, tag_ids, rejected) = cv2.aruco.detectMarkers(image, aruco_dictionary, parameters=aruco_parameters)

            # self.robots = {} # Clear dictionary every frame in case robots have disappeared

            # Check whether any tags were detected in this camera frame
            if tag_ids is not None and len(tag_ids.tolist()) > 0:

                tag_ids = list(itertools.chain(*tag_ids))
                tag_ids = [int(id) for id in tag_ids] # Convert from numpy.int32 to int

                # Process raw ArUco output
                self.processArUco(tag_ids, raw_tags)

                # Draw boundary of virtual environment based on corner tag positions
                self.drawBoundingBox(image)

                # Process and draw robots
                self.processRobots()


                self.drawBall(image)
                self.drawZones(image)
                self.drawGoals(image)
                self.timer.update()

                self.drawRobots(image)
                self.processGame(image)

                cv2.circle(image, (int(self.red_goal.centre.x), int(self.red_goal.centre.y)), 5, red, -1, lineType=cv2.LINE_AA)
                cv2.circle(image, (int(self.blue_goal.centre.x), int(self.blue_goal.centre.y)), 5, blue, -1,
                           lineType=cv2.LINE_AA)

                text = f"Time: {self.timer.getString()}"
                red_sc = str(self.blue_goal.score) # THIS IS CORRECT
                blu_sc = str(self.red_goal.score)
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 2
                thickness = 5
                textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
                position = (790, 60)
                cv2.putText(image, text, position, font, font_scale, self.timer.getColor(), thickness * 3, cv2.LINE_AA)
                cv2.putText(image, text, position, font, font_scale, black, thickness, cv2.LINE_AA)

                cv2.putText(image, blu_sc, (self.blue_goal.x2 - 40, 1000), font, font_scale * 2, white, thickness * 3, cv2.LINE_AA)
                cv2.putText(image, red_sc, (self.red_goal.x1 - 40, 1000), font, font_scale * 2, white, thickness * 3, cv2.LINE_AA)

                cv2.putText(image, blu_sc, (self.blue_goal.x2 - 40, 1000), font, font_scale * 2, blue, thickness,
                            cv2.LINE_AA)
                cv2.putText(image, red_sc, (self.red_goal.x1 - 40, 1000), font, font_scale * 2, red, thickness,
                            cv2.LINE_AA)

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
                sys.exit(1)

async def handler(websocket):
    async for packet in websocket:
        message = json.loads(packet)
        
        # Process any requests received
        reply = {}
        send_reply = False
        if tracker.calibrated:
            if "check_awake" in message:
                reply["awake"] = True
                send_reply = True

            if "get_robots" in message:
                send_reply = True
                for id, robot in tracker.robots.items():

                    reply[id] = {}
                    reply[id]["orientation"] = round(robot.orientation, 2)
                    reply[id]["role"] = robot.role.name
                    reply[id]["team"] = robot.team.name
                    reply[id]["players"] = {}
                    reply[id]["remaining_time"] = int(tracker.timer.time_left)
                    reply[id]["progress_through_zone"] = round(robot.distance, 2)

                    reply[id]["ball"] = {}
                    reply[id]["ball"]["range"] = round(robot.ball.range, 2)
                    reply[id]["ball"]["bearing"] = round(robot.ball.bearing, 2)

                    reply[id]["their_goal"] = {}
                    reply[id]["their_goal"]["range"] = round(robot.strike_goal.range, 2)
                    reply[id]["their_goal"]["bearing"] = round(robot.strike_goal.bearing, 2)

                    reply[id]["our_goal"] = {}
                    reply[id]["our_goal"]["range"] = round(robot.defend_goal.range, 2)
                    reply[id]["our_goal"]["bearing"] = round(robot.defend_goal.bearing, 2)

                    for neighbour_id, neighbour in robot.neighbours.items():

                        neighbour_robot = tracker.robots[neighbour_id]
                        reply[id]["players"][neighbour_id] = {}
                        reply[id]["players"][neighbour_id]["team"] = neighbour_robot.team.name
                        reply[id]["players"][neighbour_id]["role"] = neighbour_robot.role.name
                        reply[id]["players"][neighbour_id]["range"] = round(neighbour.range, 2)
                        reply[id]["players"][neighbour_id]["bearing"] = round(neighbour.bearing, 2)
                        reply[id]["players"][neighbour_id]["orientation"] = round(neighbour.orientation, 2)


            # Send reply, if requested
            if send_reply:
                await websocket.send(json.dumps(reply))

# TODO: Handle Ctrl+C signals
if __name__ == "__main__":
    global tracker
    tracker = Tracker()
    tracker.start()

    ##
    # Use the following iptables rule to forward port 80 to 6000 for the server to use:
    #   sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 6000
    # Alternatively, change the port below to 80 and run this Python script as root.
    ##
    start_server = websockets.serve(ws_handler=handler, host=None, port=6000)
    # start_server = websockets.serve(ws_handler=handler, host="144.32.165.233", port=6000)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server)
    loop.run_forever()
