#!/usr/bin/env python3

from robots import robots, server_none, server_york

import asyncio
import websockets
import json
import signal
import time
import sys
from enum import Enum
import time
import random
import inspect
from vector2d import Vector2D
import math
import pprint
import angles
import colorama
from colorama import Fore

"""
This function is the main loop of your application. You can make any changes you want throughout this 
file, but most of your game logic will be located in here.

First, ensure that the robot_ids list below is correctly set to the robots you wish to work with.
For example:
    robot_ids = [34, 37, 39]

When run, this script will connect to the server and then repeatedly call the main_loop() function.
The script communicates with the robots using a websockets connection. Sending data requires that you 
use Python's asynchronous I/O. If you are not familiar with this, the rule is to remember that the control
function should be declared with "async" (see the simple_obstacle_avoidance() example) and called from 
main_loop() using loop.run_until_complete(async_thing_to_run(ids))
"""

active_robots = {}
ids = []
robot_ids = [34, 37, 39]

def main_loop():
    # This line requests all robot virtual sensor data from the tracking server for the robots specified in robot_ids
    # This is stored in active_robots, a map of id -> instances of the Robot class (defined lower in this file) 
    print(Fore.GREEN + "[INFO]: Requesting data from tracking server")
    loop.run_until_complete(get_server_data())

    # Request sensor data from detected robots
    # This augments the Robot instances with their battery level and the values from each robot's proximity sensors
    # You only need to do this if you care about their battery level, or are using their proximity sensors
    print(Fore.GREEN + "[INFO]: Robots detected:", ids)
    print(Fore.GREEN + "[INFO]: Requesting data from detected robots")
    loop.run_until_complete(get_robot_data(ids))

    # Now run our behaviour
    print(Fore.GREEN + "[INFO]: Sending commands to detected robots")
    loop.run_until_complete(send_robot_commands(ids))

    print()

    # Sleep until next control cycle. We use 0.1 seconds by default so as to not flood the network.
    time.sleep(0.1)

"""
This is an example of a behaviour. You will want to replace this with a behaviour that implements your team
movements. It currently is an example of basic object avoidance.
"""
async def send_commands(robot):
    try:
        # Turn off LEDs and motors when killed. Please remember to do this!
        if kill_now():
            message = {"set_leds_colour": "off", "set_motor_speeds": {}}
            message["set_motor_speeds"]["left"] = 0
            message["set_motor_speeds"]["right"] = 0
            await robot.connection.send(json.dumps(message))

        message = {}

        """
        Construct a command message
        Robots are controlled by sending them a json dictionary which we create here using the message variable
        
        We can set the speed of the wheel motors (from -255 to 255). Setting them to the same value makes the robot go forwards
        or backwards. Setting them differently makes the robot turn. For example:
        message["set_motor_speeds"]["left"] = 100
        message["set_motor_speeds"]["right"] = 100
    
        We can also set the colour of the LED. Supported colours are "off", "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"
        message["set_leds_colour"] = "green"

        You can combine commands (i.e. setting both wheels and the LED colour in one go)

        The rest of this function is an example object avoidance behaviour which goes FORWARD unless the IR sensor
        detects something in front of it, when it will turn instead.
        """
        if robot.state == RobotState.FORWARDS:
            left = right = robot.MAX_SPEED
            if (time.time() - robot.turn_time > 0.5) and any(ir > robot.ir_threshold for ir in robot.ir_readings):
                robot.turn_time = time.time()
                robot.state = random.choice((RobotState.LEFT, RobotState.RIGHT))
            elif (time.time() - robot.regroup_time > 5):
                robot.regroup_time = time.time()
                robot.state = RobotState.REGROUP

        elif robot.state == RobotState.BACKWARDS:
            left = right = -robot.MAX_SPEED
            robot.turn_time = time.time()
            robot.state = RobotState.FORWARDS

        elif robot.state == RobotState.LEFT:
            left = -robot.MAX_SPEED
            right = robot.MAX_SPEED
            if time.time() - robot.turn_time > random.uniform(0.5, 1.0):
                robot.turn_time = time.time()
                robot.state = RobotState.FORWARDS

        elif robot.state == RobotState.RIGHT:
            left = robot.MAX_SPEED
            right = -robot.MAX_SPEED
            if time.time() - robot.turn_time > random.uniform(0.5, 1.0):
                robot.turn_time = time.time()
                robot.state = RobotState.FORWARDS

        elif robot.state == RobotState.STOP:
            left = right = 0
            robot.turn_time = time.time()
            robot.state = RobotState.FORWARDS

        elif robot.state == RobotState.REGROUP:
            message["set_leds_colour"] = "green"
            direction = Vector2D(0, 0)
            for neighbour_id, neighbour in robot.neighbours.items():
                direction += Vector2D(neighbour["range"] * math.cos(math.radians(neighbour["bearing"])),
                                      neighbour["range"] * math.sin(math.radians(neighbour["bearing"])))
            direction_polar = direction.to_polar()
            heading = angles.normalize(math.degrees(direction_polar[1]), -180, 180)
            if heading > 0:
                left = robot.MAX_SPEED
                right = 0
            else:
                left = 0
                right = robot.MAX_SPEED
            if time.time() - robot.regroup_time > random.uniform(3.0, 4.0):
                message["set_leds_colour"] = "red"
                robot.state = RobotState.FORWARDS

        message["set_motor_speeds"] = {}
        message["set_motor_speeds"]["left"] = left
        message["set_motor_speeds"]["right"] = right

        # Send command message
        await robot.connection.send(json.dumps(message))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")



# Server address, port details, globals
#---------------------------------------
server_address = server_york
server_port = 6000
robot_port = 6000

if len(server_address) == 0:
    raise Exception(f"Enter local tracking server address on line {inspect.currentframe().f_lineno - 6}, "
                    f"then re-run this script.")

server_connection = None
colorama.init(autoreset=True)


# Handle Ctrl+C termination
# https://stackoverflow.com/questions/2148888/python-trap-all-signals
#---------------------------------------------------------------------
SIGNALS_TO_NAMES_DICT = dict((getattr(signal, n), n) \
    for n in dir(signal) if n.startswith('SIG') and '_' not in n)
# https://github.com/aaugustin/websockets/issues/124
__kill_now = False

def __set_kill_now(signum, frame):
    print('\nReceived signal:', SIGNALS_TO_NAMES_DICT[signum], str(signum))
    global __kill_now
    __kill_now = True

signal.signal(signal.SIGINT, __set_kill_now)
signal.signal(signal.SIGTERM, __set_kill_now)

def kill_now() -> bool:
    global __kill_now
    return __kill_now


# Robot class and structures
#----------------------------

# Robot states to use in the example controller
class RobotState(Enum):
    FORWARDS = 1
    BACKWARDS = 2
    LEFT = 3
    RIGHT = 4
    STOP = 5
    REGROUP = 6

# Main Robot class to keep track of robot states
class Robot:

    # 3.6V should give an indication that the battery is getting low, but this value can be experimented with.
    # Battery percentage might be a better
    BAT_LOW_VOLTAGE = 3.6

    # Firmware on both robots accepts wheel velocities between -100 and 100.
    # This limits the controller to fit within that.
    MAX_SPEED = 100

    def __init__(self, robot_id):
        self.id = robot_id
        self.connection = None

        self.orientation = 0
        self.neighbours = {}
        self.tasks = {}

        self.state = RobotState.STOP
        self.ir_readings = []
        self.battery_charging = False
        self.battery_voltage = 0
        self.battery_percentage = 0

        self.turn_time = time.time()
        self.regroup_time = time.time()

        # Pi-puck IR is more sensitive than Mona, so use higher threshold for obstacle detection

        # Mona
        self.ir_threshold = 80


# Connect to websocket server of tracking server
async def connect_to_server():
    uri = f"ws://{server_address}:{server_port}"
    connection = await websockets.connect(uri)

    print("Opening connection to server: " + uri)

    awake = await check_awake(connection)

    if awake:
        print("Server is awake")
        global server_connection
        server_connection = connection
    else:
        print("Server did not respond")


# Connect to websocket server running on each of the robots
async def connect_to_robots():
    for id in active_robots.keys():
        ip = robots[id]
        if ip != '':
            uri = f"ws://{ip}:{robot_port}"
            connection = await websockets.connect(uri)

            print("Opening connection to robot:", uri)

            awake = await check_awake(connection)

            if awake:
                print(f"Robot {id} is awake")
                active_robots[id].connection = connection
            else:
                print(f"Robot {id} did not respond")
        else:
            print(f"No IP defined for robot {id}")


# Check if robot is awake by sending the "check_awake" command to its websocket server
async def check_awake(connection):
    awake = False

    try:
        message = {"check_awake": True}

        # Send request for data and wait for reply
        await connection.send(json.dumps(message))
        reply_json = await connection.recv()
        reply = json.loads(reply_json)

        # Reply should contain "awake" with value True
        awake = reply["awake"]

    except Exception as e:
        print(f"{type(e).__name__}: {e}")

    return awake


# Ask a list of robot IDs for all their sensor data (proximity + battery)
async def get_robot_data(ids):
    await message_robots(ids, get_data)


# Send all commands to a list of robots IDs (motors + LEDs)
async def send_robot_commands(ids):
    await message_robots(ids, send_commands)


# Tell a list of robot IDs to stop
async def stop_robots(ids):
    await message_robots(ids, stop_robot)


# Send a message to a list of robot IDs
# Uses multiple websockets code from:
# https://stackoverflow.com/questions/49858021/listen-to-multiple-socket-with-websockets-and-asyncio
async def message_robots(ids, function):
    loop = asyncio.get_event_loop()
    tasks = []
    for id, robot in active_robots.items():
        if id in ids:
            tasks.append(loop.create_task(function(robot)))
    await asyncio.gather(*tasks)


# Get robots' virtual sensor data from the tracking server, for our active robots
async def get_server_data():
    try:
        global ids
        # global ball
        # message = {"get_robots": True, "get_ball": True}
        message = {"get_robots": True}

        # Send request for data and wait for reply
        await server_connection.send(json.dumps(message))
        reply_json = await server_connection.recv()
        reply = json.loads(reply_json)

        pprint.PrettyPrinter(indent=4).pprint(reply)

        # ball.position = reply["ball"]["position"]
        # print(ball.position)
        # del reply['ball']

        # Filter reply from the server, based on our active robots of interest
        filtered_reply = {int(k): v for (k, v) in reply.items() if int(k) in active_robots.keys()}

        ids = list(filtered_reply.keys())

        # Receive robot virtual sensor data from the server
        for id, robot in filtered_reply.items():
            active_robots[id].orientation = robot["orientation"]
            # Filter out any neighbours that aren't our active robots
            active_robots[id].neighbours = {k: v for (k, v) in robot["neighbours"].items() if int(k) in active_robots.keys()}
            active_robots[id].tasks = robot["tasks"]
            print(f"Robot {id}")
            print(f"Orientation = {active_robots[id].orientation}")
            print(f"Neighbours = {active_robots[id].neighbours}")
            print(f"Tasks = {active_robots[id].tasks}")
            print()


    except Exception as e:
        print(f"{type(e).__name__}: {e}")


# Stop robot from moving and turn off its LEDs
async def stop_robot(robot):
    try:
        # Turn off LEDs and motors when killed
        message = {"set_leds_colour": "off", "set_motor_speeds": {}}
        message["set_motor_speeds"]["left"] = 0
        message["set_motor_speeds"]["right"] = 0
        await robot.connection.send(json.dumps(message))

        # Send command message
        await robot.connection.send(json.dumps(message))
    except Exception as e:
        print(f"{type(e).__name__}: {e}")


# Get IR and battery readings from robot
async def get_data(robot):
    try:
        message = {"get_ir": True, "get_battery": True}

        # Send request for data and wait for reply
        await robot.connection.send(json.dumps(message))
        reply_json = await robot.connection.recv()
        reply = json.loads(reply_json)

        robot.ir_readings = reply["ir"]

        robot.battery_voltage = reply["battery"]["voltage"]
        robot.battery_percentage = reply["battery"]["percentage"]

        print(f"[Robot {robot.id}] IR readings: {robot.ir_readings}")
        print("[Robot {}] Battery: {:.2f}V, {}%" .format(robot.id,
                                                         robot.battery_voltage,
                                                         robot.battery_percentage))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")



# Main entry point for robot control client sample code
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    loop.run_until_complete(connect_to_server())

    if server_connection is None:
        print(Fore.RED + "[ERROR]: No connection to server")
        sys.exit(1)

    assert len(robot_ids) > 0

    # Create Robot objects
    for robot_id in robot_ids:
        if robots[robot_id] != '':
            active_robots[robot_id] = Robot(robot_id)
        else:
            print(f"No IP defined for robot {robot_id}")

    # Create websockets connections to robots
    print(Fore.GREEN + "[INFO]: Connecting to robots")
    loop.run_until_complete(connect_to_robots())

    if not active_robots:
        print(Fore.RED + "[ERROR]: No connection to robots")
        sys.exit(1)

    # Only communicate with robots that were successfully connected to
    while True:
        main_loop()

        if kill_now():
            loop.run_until_complete(stop_robots(robot_ids))  # Kill all robots, even if not visible
            break
