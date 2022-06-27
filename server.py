#!/usr/bin/env python3

import sys
import cv2
import math
from camera import *
from vector2d import Vector2D
import itertools
import random
import time
from enum import Enum

red = (0, 0, 255)
blue = (255, 150, 0)
green = (0, 255, 0)
magenta = (255, 0, 255)
cyan = (255, 255, 0)
yellow = (50, 255, 255)
black = (0, 0, 0)
white = (255, 255, 255)

class Team(Enum):
    RED = 1
    BLUE = 2

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

class Task:
    def __init__(self, id, workers, position, radius, time_limit):
        self.id = id
        self.workers = workers
        self.position = position
        self.radius = radius
        self.time_limit = time_limit
        self.counter = time_limit
        self.completed = False
        self.failed = False
        self.start_time = time.time()
        self.arrival_time = time.time()
        self.completing = False
        self.team = None

class Tracker():

    def __init__(self):
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
        self.tasks = {}
        self.task_counter = 0
        self.score_red = 0 # Even
        self.score_blue = 0 # Odd
        self.start_time = time.time()
        self.running = False
        self.time_limit = 180
        self.task_last_placed = time.time()

    def run(self):
        while True:

            if self.running and (time.time() - self.start_time > self.time_limit):
                self.running = False

            image = self.camera.get_frame()
            overlay = image.copy()
            
            aruco_dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_100)
            aruco_parameters = cv2.aruco.DetectorParameters_create()

            (raw_tags, tag_ids, rejected) = cv2.aruco.detectMarkers(image, aruco_dictionary, parameters=aruco_parameters)

            self.robots = {} # Clear dictionary every frame in case robots have disappeared

            # Check whether any tags were detected in this camera frame
            if tag_ids is not None and len(tag_ids.tolist()) > 0:

                tag_ids = list(itertools.chain(*tag_ids))
                tag_ids = [int(id) for id in tag_ids] # Convert from numpy.int32 to int

                # Process raw ArUco output
                for id, raw_tag in zip(tag_ids, raw_tags):

                    tag = Tag(id, raw_tag)

                    if self.calibrated:
                        if tag.id != 0: # Reserved tag ID for corners
                            position = Vector2D(tag.centre.x / self.scale_factor, tag.centre.y / self.scale_factor) # Convert pixel coordinates to metres
                            self.robots[id] = Robot(tag, position)
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

                                self.corner_distance_pixels = math.dist([self.min_x, self.min_y], [self.max_x, self.max_y]) # Euclidean distance between corner tags in pixels
                                self.scale_factor = self.corner_distance_pixels / self.corner_distance_metres
                                x = ((self.max_x - self.min_x) / 2) / self.scale_factor # Convert to metres
                                y = ((self.max_y - self.min_y) / 2) / self.scale_factor # Convert to metres
                                self.centre = Vector2D(x, y)
                                self.calibrated = True

                            self.num_corner_tags = self.num_corner_tags + 1

                if self.calibrated:

                    # Draw boundary of virtual environment based on corner tag positions
                    cv2.rectangle(image, (self.min_x, self.min_y), (self.max_x, self.max_y), green, 1, lineType=cv2.LINE_AA)
            
                    # Process robots
                    for id, robot in self.robots.items():

                        # Draw tag
                        tag = robot.tag

                        # Draw border of tag
                        cv2.line(image, (tag.tl.x, tag.tl.y), (tag.tr.x, tag.tr.y), green, 1, lineType=cv2.LINE_AA)
                        cv2.line(image, (tag.tr.x, tag.tr.y), (tag.br.x, tag.br.y), green, 1, lineType=cv2.LINE_AA)
                        cv2.line(image, (tag.br.x, tag.br.y), (tag.bl.x, tag.bl.y), green, 1, lineType=cv2.LINE_AA)
                        cv2.line(image, (tag.bl.x, tag.bl.y), (tag.tl.x, tag.tl.y), green, 1, lineType=cv2.LINE_AA)
                        
                        # Draw circle on centre point
                        cv2.circle(image, (tag.centre.x, tag.centre.y), 35, red if (id % 2 == 0) else blue, -1, lineType=cv2.LINE_AA)

                    for id, robot in self.robots.items():

                        tag = robot.tag

                        # Draw line from centre point to front of tag
                        forward_point = ((tag.front - tag.centre) * 2) + tag.centre
                        cv2.line(image, (tag.centre.x, tag.centre.y), (forward_point.x, forward_point.y), black, 10, lineType=cv2.LINE_AA)
                        cv2.line(image, (tag.centre.x, tag.centre.y), (forward_point.x, forward_point.y), green, 3, lineType=cv2.LINE_AA)

                        # Draw tag ID
                        text = str(tag.id)
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 1.5
                        thickness = 4
                        textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
                        position = (int(tag.centre.x - textsize[0]/2), int(tag.centre.y + textsize[1]/2))
                        cv2.putText(image, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                        cv2.putText(image, text, position, font, font_scale, white, thickness, cv2.LINE_AA)
                        cv2.putText(overlay, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                        cv2.putText(overlay, text, position, font, font_scale, white, thickness, cv2.LINE_AA)

                    if self.running:

                        # Create any new tasks, if necessary
                        if len(self.tasks) < 10:
                            time_now = time.time()
                            if time_now - self.task_last_placed > random.randint(1, 10):
                                id = self.task_counter
                                placed = False
                                while not placed:
                                    overlaps = False
                                    workers = random.randint(1, 2)
                                    radius = math.sqrt(workers) * 0.1
                                    min_x_metres = self.min_x / self.scale_factor
                                    max_x_metres = self.max_x / self.scale_factor
                                    min_y_metres = self.min_y / self.scale_factor
                                    max_y_metres = self.max_y / self.scale_factor
                                    x = random.uniform(min_x_metres + radius, max_x_metres - radius)
                                    y = random.uniform(min_y_metres + radius, max_y_metres - radius)
                                    position = Vector2D(x, y) # In metres

                                    for other_task in self.tasks.values():
                                        overlap = radius + other_task.radius
                                        if position.distance_to(other_task.position) < overlap:
                                            overlaps = True
                                    
                                    if not overlaps:
                                        placed = True
                                        self.task_last_placed = time_now

                                time_limit = 20 * workers # 20 seconds per robot
                                self.tasks[id] = Task(id, workers, position, radius, time_limit)
                                self.task_counter = self.task_counter + 1

                        # Iterate over tasks
                        for task_id, task in self.tasks.items():

                            task.red_robots = set()
                            task.blue_robots = set()

                            # Check whether robot is within range
                            for robot_id, robot in self.robots.items():
                                distance = task.position.distance_to(robot.position)

                                if distance < task.radius:
                                    if robot_id % 2 == 0:
                                        task.red_robots.add(robot_id)
                                    else:
                                        task.blue_robots.add(robot_id)

                            time_now = time.time()
                            
                            if len(task.red_robots) >= task.workers or len(task.blue_robots) >= task.workers:
                                if not task.completing:
                                    if len(task.red_robots) > len(task.blue_robots):
                                        task.team = Team.RED
                                    else:
                                        task.team = Team.BLUE
                                    task.completing = True
                                    task.arrival_time = time.time()
                                elif time_now - task.arrival_time > 5:
                                    task.completed = True
                            elif task.completing:
                                task.completing = False

                            pixel_radius = int(task.radius * self.scale_factor)
                            x = int(task.position.x * self.scale_factor)
                            y = int(task.position.y * self.scale_factor)

                            # Draw task timer
                            if not task.completing:
                                task.elapsed_time = time_now - task.start_time
                                if task.elapsed_time > 1:
                                    task.start_time = time_now
                                    task.counter = task.counter - 1
                                    if task.counter <= 1:
                                        task.failed = True

                            cv2.circle(overlay, (x, y), int((pixel_radius / task.time_limit) * task.counter), cyan, -1, lineType=cv2.LINE_AA)

                            if task.completing:
                                cv2.ellipse(overlay, (x, y), (pixel_radius, pixel_radius), 0, -90, -90 + (((time_now - task.arrival_time) / 5) * 360), green, cv2.FILLED)

                            if task.completing:
                                colour = green
                            else:
                                colour = magenta

                            # Draw task boundary
                            cv2.circle(image, (x, y), pixel_radius, black, 10, lineType=cv2.LINE_AA)
                            cv2.circle(image, (x, y), pixel_radius, colour, 5, lineType=cv2.LINE_AA)
                            cv2.circle(overlay, (x, y), pixel_radius, black, 10, lineType=cv2.LINE_AA)
                            cv2.circle(overlay, (x, y), pixel_radius, colour, 5, lineType=cv2.LINE_AA)

                            # Draw task workers
                            text = str(task.workers * 5)
                            font = cv2.FONT_HERSHEY_SIMPLEX
                            font_scale = 1.5
                            thickness = 4
                            textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
                            position = (int(x - textsize[0]/2), int(y + textsize[1]/2))
                            cv2.putText(image, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                            cv2.putText(image, text, position, font, font_scale, colour, thickness, cv2.LINE_AA)
                            cv2.putText(overlay, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                            cv2.putText(overlay, text, position, font, font_scale, colour, thickness, cv2.LINE_AA)

                        # Delete completed tasks
                        for task_id in list(self.tasks.keys()):
                            task = self.tasks[task_id]
                            if task.completed:
                                if task.team == Team.RED:
                                    self.score_red = self.score_red + (task.workers * 5)
                                else: # task.team == Team.BLUE:
                                    self.score_blue = self.score_blue + (task.workers * 5)

                                del self.tasks[task_id]
                            elif task.failed:
                                del self.tasks[task_id]

                    # Draw the score
                    text = f"Score: {self.score_red}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 2
                    thickness = 5
                    textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    position = (10, 60)
                    cv2.putText(image, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                    cv2.putText(image, text, position, font, font_scale, red, thickness, cv2.LINE_AA)
                    cv2.putText(overlay, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                    cv2.putText(overlay, text, position, font, font_scale, red, thickness, cv2.LINE_AA)

                    position = (10, 130)
                    text = f"Score: {self.score_blue}"
                    cv2.putText(image, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                    cv2.putText(image, text, position, font, font_scale, blue, thickness, cv2.LINE_AA)
                    cv2.putText(overlay, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                    cv2.putText(overlay, text, position, font, font_scale, blue, thickness, cv2.LINE_AA)

                    # Draw the timer
                    time_remaining = 0
                    if self.running:
                        time_remaining = int(self.time_limit + self.start_time - time.time())
                    mins, secs = divmod(time_remaining, 60)
                    timer = '{:02d}:{:02d}'.format(mins, secs)
                    text = f"Timer: {timer}"
                    textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    position = (image.shape[1] - textsize[0] - 10, 60)
                    cv2.putText(image, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                    cv2.putText(image, text, position, font, font_scale, yellow, thickness, cv2.LINE_AA)
                    cv2.putText(overlay, text, position, font, font_scale, black, thickness * 3, cv2.LINE_AA)
                    cv2.putText(overlay, text, position, font, font_scale, yellow, thickness, cv2.LINE_AA)

                    if self.running:
                        colour = green
                        text = f"GO"
                    else:
                        colour = red
                        text = f"STOP"

                    font_scale = 3
                    thickness = 10
                    textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    position = (int(image.shape[1]/2 - textsize[0]/2), textsize[1] + 30)
                    cv2.putText(image, text, position, font, font_scale, black, thickness * 2, cv2.LINE_AA)
                    cv2.putText(image, text, position, font, font_scale, colour, thickness, cv2.LINE_AA)
                    cv2.putText(overlay, text, position, font, font_scale, black, thickness * 2, cv2.LINE_AA)
                    cv2.putText(overlay, text, position, font, font_scale, colour, thickness, cv2.LINE_AA)

                    # Transparency for overlaid augments
                    alpha = 0.3
                    image = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)

            window_name = 'Knightmare'

            # screen = screeninfo.get_monitors()[0]
            # width, height = screen.width, screen.height
            # image = cv2.resize(image, (width, height))
            # cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
            # cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

            cv2.imshow(window_name, image)

            key = cv2.waitKey(1)

            if key == ord('p'):
                if self.running == False:
                    self.running = True
                    self.score_red = 0
                    self.score_blue = 0
                    self.tasks = {}
                    self.start_time = time.time()

            if key == ord('r'):
                self.running = False
                self.score_red = 0
                self.score_blue = 0
                self.tasks = {}

            if key == ord('q'):
                sys.exit()


if __name__ == "__main__":
    global tracker
    tracker = Tracker()
    tracker.run()
