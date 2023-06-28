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

import colorama
from colorama import Fore
colorama.init(autoreset=True)

def foraging_strategy(food_items, opponents):

    target = None

    print(food_items)
    print(opponents)

    for food in food_items:
        print(food)

        if target is None:
            target = food
            continue
        
        if (food.value >= target.value) and (food.distance < target.distance):
            target = food

    print("TARGET:", target)
    return target

    
class Food:
    def __init__(self, food_id, food_value, food_distance, food_angle):
        self.id = food_id
        self.value = food_value
        self.distance = food_distance
        self.angle = food_angle

    def __repr__(self):
        return f'Food(ID: {self.id}, Value: {self.value}, Distance: {self.distance}, Angle: {self.angle})'
    

class Opponent:
    def __init__(self, opponent_id, opponent_distance, opponent_angle):
        self.id = opponent_id
        self.distance = opponent_distance
        self.angle = opponent_angle

    def __repr__(self):
        return f'Opponent(ID: {self.id}, Distance: {self.distance}, Angle: {self.angle})'


##
# Replace `server_none` with one of `server_york`, `server_sheffield`, or `server_manchester` here,
#  or specify a custom server IP address as a string.
# All ports should remain at 80.
##
server_address = server_york
server_port = 6000
robot_port = 6000
##

if len(server_address) == 0:
    raise Exception(f"Enter local tracking server address on line {inspect.currentframe().f_lineno - 6}, "
                    f"then re-run this script.")


# Persistent Websockets!!!!!!!!!!!!!!!!
# https://stackoverflow.com/questions/59182741/python-websockets-lib-client-persistent-connection-with-class-implementation


##
# Handle Ctrl+C termination
# https://stackoverflow.com/questions/2148888/python-trap-all-signals

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

# Ctrl+C termination handled
##


server_connection = None
active_robots = {}
ids = []


# Robot states to use in the controller
class RobotState(Enum):
    FORWARDS = 1
    BACKWARDS = 2
    LEFT = 3
    RIGHT = 4
    STOP = 5
    FORAGING = 6


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

        self.teleop = False
        self.state = RobotState.STOP
        self.ir_readings = []
        self.battery_charging = False
        self.battery_voltage = 0
        self.battery_percentage = 0

        self.left_speed = 0
        self.right_speed = 0
        self.turn_time = time.time()

        # Pi-puck IR is more sensitive than Mona, so use higher threshold for obstacle detection
        if robot_id < 31:
            # Pi-puck
            self.ir_threshold = 200
        else:
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
        message = {"get_robots": True}

        # Send request for data and wait for reply
        await server_connection.send(json.dumps(message))
        reply_json = await server_connection.recv()
        reply = json.loads(reply_json)

        # Filter reply from the server, based on our active robots of interest
        filtered_reply = {int(k): v for (k, v) in reply.items() if int(k) in active_robots.keys()}

        ids = list(filtered_reply.keys())

        # Receive robot virtual sensor data from the server
        for id, robot in filtered_reply.items():
            active_robots[id].orientation = robot["orientation"]
            # Filter out any neighbours that aren't our active robots
            # active_robots[id].neighbours = {k: v for (k, v) in robot["neighbours"].items() if int(k) in active_robots.keys()}
            active_robots[id].neighbours = robot["neighbours"]
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


# Send motor and LED commands to robot
# This function also performs the obstacle avoidance and teleop algorithm state machines
async def send_commands(robot):
    try:
        # Turn off LEDs and motors when killed
        if kill_now():
            message = {"set_leds_colour": "off", "set_motor_speeds": {}}
            message["set_motor_speeds"]["left"] = 0
            message["set_motor_speeds"]["right"] = 0
            await robot.connection.send(json.dumps(message))

        food_items = []        

        for task_id, task in robot.tasks.items():
            food_value = task["workers"]
            food_distance = task["range"]
            food_angle = task["bearing"]
            food_items.append(Food(task_id, food_value, round(food_distance, 2), round(food_angle, 2)))

        opponents = []

        for neighbour_id, neighbour in robot.neighbours.items():
            opponent_distance = neighbour["range"]
            opponent_angle = neighbour["bearing"]
            opponents.append(Opponent(neighbour_id, round(opponent_distance, 2), round(opponent_angle, 2)))

        target = foraging_strategy(food_items, opponents)

        # Construct command message
        message = {}

        print("RobotState:", robot.state)

        # Autonomous mode
        if robot.state == RobotState.FORWARDS:
            robot.left_speed = robot.right_speed = robot.MAX_SPEED
            if (time.time() - robot.turn_time > 0.5) and any(ir > robot.ir_threshold for ir in robot.ir_readings):
                robot.turn_time = time.time()
                robot.state = random.choice((RobotState.LEFT, RobotState.RIGHT))
            else:
                if target is not None:
                    robot.state = RobotState.FORAGING
        if robot.state == RobotState.BACKWARDS:
            robot.left_speed = robot.right_speed = -robot.MAX_SPEED
            robot.turn_time = time.time()
            robot.state = RobotState.FORWARDS
        if robot.state == RobotState.LEFT:
            robot.left_speed = -robot.MAX_SPEED
            robot.right_speed = robot.MAX_SPEED
            if time.time() - robot.turn_time > random.uniform(0.5, 1.0):
                robot.turn_time = time.time()
                robot.state = RobotState.FORWARDS
        if robot.state == RobotState.RIGHT:
            robot.left_speed = robot.MAX_SPEED
            robot.right_speed = -robot.MAX_SPEED
            if time.time() - robot.turn_time > random.uniform(0.5, 1.0):
                robot.turn_time = time.time()
                robot.state = RobotState.FORWARDS
        if robot.state == RobotState.STOP:
            robot.left_speed = robot.right_speed = 0
            robot.turn_time = time.time()
            robot.state = RobotState.FORWARDS
        if robot.state == RobotState.FORAGING:

            if target is not None:

                bearing = target.angle
                turn_threshold_angle = 5
                min_speed = int(robot.MAX_SPEED * 0.7)

                angle_ratio = abs(bearing)/180
                scaled_speed = (robot.MAX_SPEED - min_speed) * angle_ratio
                speed = int(scaled_speed + min_speed)

                print("bearing:", round(bearing, 2))
                print("angle_ratio:", round(angle_ratio, 2))
                print("max_speed:", robot.MAX_SPEED)
                print("min_speed:", min_speed)
                print("scaled_speed:", round(scaled_speed, 2))
                print("speed:", speed)

                if bearing > turn_threshold_angle:
                    robot.left_speed = speed
                    robot.right_speed = 0
                elif bearing < -turn_threshold_angle:
                    robot.left_speed = 0
                    robot.right_speed = speed
                else:
                    robot.left_speed = robot.right_speed = robot.MAX_SPEED
            else:
                robot.state = RobotState.FORWARDS

            if (time.time() - robot.turn_time > 0.5) and any(ir > robot.ir_threshold for ir in robot.ir_readings):
                robot.turn_time = time.time()
                robot.state = random.choice((RobotState.LEFT, RobotState.RIGHT))


        message["set_motor_speeds"] = {}
        message["set_motor_speeds"]["left"] = robot.left_speed
        message["set_motor_speeds"]["right"] = robot.right_speed

        # Set RGB LEDs based on battery voltage
        if robot.battery_voltage < robot.BAT_LOW_VOLTAGE:
            message["set_leds_colour"] = "red"
        else:
            message["set_leds_colour"] = "green"

        # Send command message
        await robot.connection.send(json.dumps(message))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")


# Main entry point for robot control client sample code
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    loop.run_until_complete(connect_to_server())

    if server_connection is None:
        print(Fore.RED + "[ERROR]: No connection to server")
        sys.exit(1)

    # Specify robot IDs to work with here. For example for robots 11-15 use:
    #  robot_ids = range(11, 16)
    robot_ids = [31]

    if len(robot_ids) == 0:
        raise Exception(f"Enter range of robot IDs to control on line {inspect.currentframe().f_lineno - 3}, "
                        f"then re-run this script.")

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
        # Request all robot virtual sensor data from the tracking server
        print(Fore.GREEN + "[INFO]: Requesting data from tracking server")
        loop.run_until_complete(get_server_data())

        # Request sensor data from detected robots
        print(Fore.GREEN + "[INFO]: Robots detected:", ids)
        print(Fore.GREEN + "[INFO]: Requesting data from detected robots")
        loop.run_until_complete(get_robot_data(ids))

        # Calculate next step of control algorithm, and send commands to robots
        print(Fore.GREEN + "[INFO]: Sending commands to detected robots")
        loop.run_until_complete(send_robot_commands(ids))

        print()

        # TODO: Close websocket connections
        if kill_now():
            loop.run_until_complete(stop_robots(robot_ids))  # Kill all robots, even if not visible
            break

        # Sleep until next control cycle
        time.sleep(0.1)
