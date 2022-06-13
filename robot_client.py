#!/usr/bin/env python3

from robots import robots, server_none, server_york, server_manchester, server_sheffield

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


##
# Replace `server_none` with one of `server_york`, `server_sheffield`, or `server_manchester` here,
#  or specify a custom server IP address as a string.
# All ports should remain at 80.
##
server_address = server_none
server_port = 80
robot_port = 80
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

        self.teleop = False
        self.state = RobotState.STOP
        self.ir_readings = []
        self.battery_charging = False
        self.battery_voltage = 0
        self.battery_percentage = 0

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


# Get all robots' virtual sensor data from the tracking server
async def get_server_data():
    try:
        global ids
        message = {"get_robots": True}

        # Send request for data and wait for reply
        await server_connection.send(json.dumps(message))
        reply_json = await server_connection.recv()
        reply = json.loads(reply_json)

        # Get returned list of IDs as ints
        ids = list(reply.keys())
        ids = [int(id) for id in ids]

        # Loop through robots that the server is tracking
        for key, robot in reply.items():
            id = int(key)
            # Filter based on our active robots of interest
            if id in active_robots.keys():
                # Receive robot virtual sensor data from the server
                active_robots[id].orientation = robot["orientation"]
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

        # Construct command message
        message = {}

        if robot.teleop:
            # Teleoperation mode
            message["set_leds_colour"] = "blue"
            if robot.state == RobotState.FORWARDS:
                left = right = robot.MAX_SPEED
            elif robot.state == RobotState.BACKWARDS:
                left = right = -robot.MAX_SPEED
            elif robot.state == RobotState.LEFT:
                left = -robot.MAX_SPEED * 0.8
                right = robot.MAX_SPEED * 0.8
            elif robot.state == RobotState.RIGHT:
                left = robot.MAX_SPEED * 0.8
                right = -robot.MAX_SPEED * 0.8
            elif robot.state == RobotState.STOP:
                left = right = 0
        else:
            # Autonomous mode
            if robot.state == RobotState.FORWARDS:
                left = right = robot.MAX_SPEED
                if (time.time() - robot.turn_time > 0.5) and any(ir > robot.ir_threshold for ir in robot.ir_readings):
                    robot.turn_time = time.time()
                    robot.state = random.choice((RobotState.LEFT, RobotState.RIGHT))
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

        message["set_motor_speeds"] = {}
        message["set_motor_speeds"]["left"] = left
        message["set_motor_speeds"]["right"] = right

        # Set RGB LEDs based on battery voltage
        if robot.battery_voltage < robot.BAT_LOW_VOLTAGE:
            message["set_leds_colour"] = "red"
        else:
            message["set_leds_colour"] = "green"

        # Send command message
        await robot.connection.send(json.dumps(message))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")


# Menu state for teleop control input
class MenuState(Enum):
    START = 1
    SELECT = 2
    DRIVE = 3


# Send message to a websocket server
async def send_message(websocket, message):
    await websocket.send(json.dumps({"prompt": message}))


# Handle message received on the websocket server
# Used for teleoperation code, which is controlled by running teleop_client.py in a separate terminal.
async def handler(websocket):
    state = MenuState.START
    robot_id = ""
    valid_robots = list(active_robots.keys())
    forwards = "w"
    backwards = "s"
    left = "a"
    right = "d"
    stop = " "
    release = "q"

    async for packet in websocket:
        message = json.loads(packet)
        if "key" in message:
            key = message["key"]
            if key == "teleop_start":
                state = MenuState.START
            elif key == "teleop_stop":
                if state == MenuState.DRIVE:
                    id = int(robot_id)
                    active_robots[id].teleop = False
                    active_robots[id].state = RobotState.STOP

            if state == MenuState.START:
                await send_message(websocket, f"\r\nEnter robot ID ({valid_robots}), then press return: ")
                robot_id = ""
                state = MenuState.SELECT
            elif state == MenuState.SELECT:
                if key == "\r":
                    valid = False
                    try:
                        if int(robot_id) in valid_robots:
                            valid = True
                            await send_message(websocket, f"\r\nControlling robot ({release} to release): " + robot_id)
                            await send_message(websocket, f"\r\nControls: Forwards = {forwards}; Backwards = {backwards}; Left = {left}; Right = {right}; Stop = SPACE")
                            active_robots[int(robot_id)].teleop = True
                            state = MenuState.DRIVE
                    except ValueError:
                        pass

                    if not valid:
                        await send_message(websocket, "\r\nInvalid robot ID, try again: ")
                        robot_id = ""
                        state = MenuState.SELECT
                else:
                    await send_message(websocket, key)
                    robot_id = robot_id + key
            elif state == MenuState.DRIVE:
                id = int(robot_id)
                if key == release:
                    await send_message(websocket, "\r\nReleasing control of robot: " + robot_id)
                    active_robots[id].teleop = False
                    active_robots[id].state = RobotState.STOP
                    state = MenuState.START
                elif key == forwards:
                    await send_message(websocket, "\r\nDriving forwards")
                    active_robots[id].state = RobotState.FORWARDS
                elif key == backwards:
                    await send_message(websocket, "\r\nDriving backwards")
                    active_robots[id].state = RobotState.BACKWARDS
                elif key == left:
                    await send_message(websocket, "\r\nTurning left")
                    active_robots[id].state = RobotState.LEFT
                elif key == right:
                    await send_message(websocket, "\r\nTurning right")
                    active_robots[id].state = RobotState.RIGHT
                elif key == stop:
                    await send_message(websocket, "\r\nStopping")
                    active_robots[id].state = RobotState.STOP
                else:
                    await send_message(websocket, "\r\nUnrecognised command")


# Main entry point for robot control client sample code
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    loop.run_until_complete(connect_to_server())

    if server_connection is None:
        print(Fore.RED + "[ERROR]: No connection to server")
        sys.exit(1)

    # Specify robot IDs to work with here. For example for robots 11-15 use:
    #  robot_ids = range(11, 16)
    robot_ids = range(0, 0)

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

    # Listen for any keyboard input from teleop websocket client
    print(Fore.GREEN + "[INFO]: Starting teleop server")
    start_server = websockets.serve(ws_handler=handler, host=None, port=7000, ping_interval=None, ping_timeout=None)
    loop.run_until_complete(start_server)

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
