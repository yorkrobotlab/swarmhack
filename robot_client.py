#!/usr/bin/env python3

from robots import robots

import asyncio
import websockets
import json
import signal
import time
import sys
from enum import Enum

import colorama
from colorama import Fore

colorama.init(autoreset=True)

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


server_address = "144.32.165.233"
server_port = 80
robot_port = 80

server_connection = None
active_robots = {}
ids = []


class RobotState(Enum):
    FORWARDS = 1
    BACKWARDS = 2
    LEFT = 3
    RIGHT = 4
    STOP = 5


class Robot:

    BAT_LOW_VOLTAGE = 3.6
    MAX_SPEED = 100
    ir_threshold = 300
    weights_left = [-10, -10, -5, 0, 0, 5, 10, 10]
    weights_right = [-1 * x for x in weights_left]

    def __init__(self, id):
        self.id = id
        self.connection = None

        self.orientation = 0
        self.neighbours = {}

        self.teleop = False
        self.state = RobotState.STOP
        self.ir_readings = []
        self.battery_charging = False
        self.battery_voltage = 0
        self.battery_percentage = 0


async def connect_to_server():
    uri = f"ws://{server_address}:{server_port}"
    connection = websockets.connect(uri)

    print("Opening connection to server: " + uri)

    awake = await check_awake(connection)

    if awake:
        print("Server is awake")
        global server_connection
        server_connection = connection
    else:
        print("Server did not respond")


async def connect_to_robots(ids):
    for id in ids:
        ip = robots[id]
        if ip != '':
            uri = f"ws://{ip}:{robot_port}"
            connection = websockets.connect(uri)

            print("Opening connection to robot:", uri)

            awake = await check_awake(connection)

            if awake:
                print(f"Robot {id} is awake")
                active_robots[id].connection = connection
            else:
                print(f"Robot {id} did not respond")
        else:
            print(f"No IP defined for robot {id}")


async def check_awake(connection):
    awake = False

    try:
        async with connection as websocket:
            message = {"check_awake": True}

            # Send request for data and wait for reply
            await websocket.send(json.dumps(message))
            reply_json = await websocket.recv()
            reply = json.loads(reply_json)

            awake = reply["awake"]

    except Exception as e:
        print(f"{type(e).__name__}: {e}")

    return awake


async def get_robot_data(ids):
    await message_robots(ids, get_data)


async def send_robot_commands(ids):
    await message_robots(ids, send_commands)


async def stop_robots(ids):
    await message_robots(ids, stop_robot)


# https://stackoverflow.com/questions/49858021/listen-to-multiple-socket-with-websockets-and-asyncio
async def message_robots(ids, function):
    loop = asyncio.get_event_loop()

    tasks = []

    for id, robot in active_robots.items():
        if id in ids:
            tasks.append(loop.create_task(function(robot)))
    
    await asyncio.gather(*tasks)


async def get_server_data():
    try:
        async with server_connection as websocket:

            global ids
            message = {"get_robots": True}

            # Send request for data and wait for reply
            await websocket.send(json.dumps(message))
            reply_json = await websocket.recv()
            reply = json.loads(reply_json)

            ids = list(reply.keys())
            ids = [int(id) for id in ids]

            for id, robot in reply.items():
                id = int(id)  # ID is sent as an integer - why is this necessary?

                if id in active_robots.keys():  # Filter based on robots of interest

                    active_robots[id].orientation = robot["orientation"]
                    active_robots[id].neighbours = robot["neighbours"]
                
                    print(f"Robot {id}")
                    print(f"Orientation: {active_robots[id].orientation}")
                    print(f"Neighbours = {active_robots[id].neighbours}")
                    print()

    except Exception as e:
        print(f"{type(e).__name__}: {e}")


async def stop_robot(robot):
    try:
        async with robot.connection as websocket:

            # Turn of LEDs and motors when killed
            message = {"set_leds_colour": "off", "set_outer_leds": [0] * 8, "set_motor_speeds": {}}
            message["set_motor_speeds"]["left"] = 0
            message["set_motor_speeds"]["right"] = 0
            await websocket.send(json.dumps(message))

            # Send command message
            await websocket.send(json.dumps(message))
    except Exception as e:
        print(f"{type(e).__name__}: {e}")


async def get_data(robot):
    try:
        async with robot.connection as websocket:

            message = {"get_ir": True, "get_battery": True}

            # Send request for data and wait for reply
            await websocket.send(json.dumps(message))
            reply_json = await websocket.recv()
            reply = json.loads(reply_json)

            robot.ir_readings = reply["ir"]

            robot.battery_voltage = reply["battery"]["voltage"]
            robot.battery_percentage = reply["battery"]["percentage"]

            print(f"[Robot {robot.id}] IR readings: {robot.ir_readings}")
            print("[Robot {}] Battery: {:.2f}V, {:.2f}%" .format(robot.id,
                                                                 robot.battery_voltage,
                                                                 robot.battery_percentage * 100))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")


async def send_commands(robot):
    try:
        async with robot.connection as websocket:

            # Turn of LEDs and motors when killed
            if kill_now():
                message = {"set_leds_colour": "off", "set_motor_speeds": {}}
                message["set_motor_speeds"]["left"] = 0
                message["set_motor_speeds"]["right"] = 0
                await websocket.send(json.dumps(message))

            # Construct command message
            message = {}

            if robot.teleop:
                message["set_leds_colour"] = "blue"
                if robot.state == RobotState.FORWARDS:
                    left = right = robot.MAX_SPEED
                elif robot.state == RobotState.BACKWARDS:
                    left = right = -robot.MAX_SPEED
                elif robot.state == RobotState.LEFT:
                    left = -robot.MAX_SPEED
                    right = robot.MAX_SPEED
                elif robot.state == RobotState.RIGHT:
                    left = robot.MAX_SPEED
                    right = -robot.MAX_SPEED
                elif robot.state == RobotState.STOP:
                    left = right = 0
            else:
                # Autonomous mode
                left = right = robot.MAX_SPEED / 2

                for i, reading in enumerate(robot.ir_readings):
                    if reading > robot.ir_threshold:
                        # Set wheel speeds to avoid detected obstacles
                        left += robot.weights_left[i] * reading
                        right += robot.weights_right[i] * reading

                # Set Pi-puck RGB LEDs based on battery voltage
                if robot.battery_voltage < robot.BAT_LOW_VOLTAGE:
                    message["set_leds_colour"] = "red"
                else:
                    message["set_leds_colour"] = "green"

                # Clamp wheel speeds between min/max values
                if left > robot.MAX_SPEED:
                    left = robot.MAX_SPEED
                elif left < -robot.MAX_SPEED:
                    left = -robot.MAX_SPEED

                if right > robot.MAX_SPEED:
                    right = robot.MAX_SPEED
                elif right < -robot.MAX_SPEED:
                    right = -robot.MAX_SPEED

            message["set_motor_speeds"] = {}
            message["set_motor_speeds"]["left"] = left
            message["set_motor_speeds"]["right"] = right

            # Send command message
            await websocket.send(json.dumps(message))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")


class MenuState(Enum):
    START = 1
    SELECT = 2
    DRIVE = 3


async def send_message(websocket, message):
    await websocket.send(json.dumps({"prompt": message}))


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
        # print(message)

        if "key" in message:

            key = message["key"]

            if key == "teleop_start":
                state = MenuState.START

            if key == "teleop_stop":
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


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    loop.run_until_complete(connect_to_server())

    if server_connection is None:
        print(Fore.RED + "[ERROR]: No connection to server")
        sys.exit(1)

    # Specify robots to work with
    # robot_ids = range(1, 11)
    robot_ids = [7]

    for robot_id in robot_ids:
        active_robots[robot_id] = Robot(robot_id)

    print(Fore.GREEN + "[INFO]: Connecting to robots")
    loop.run_until_complete(connect_to_robots(robot_ids))

    if not active_robots:
        print(Fore.RED + "[ERROR]: No connection to robots")
        sys.exit(1)

    # Listen for keyboard input from teleop websocket client
    print(Fore.GREEN + "[INFO]: Starting teleop server")
    start_server = websockets.serve(ws_handler=handler, host=None, port=7000, ping_interval=None, ping_timeout=None)
    loop.run_until_complete(start_server)

    # Only communicate with robots that were successfully connected to
    while True:

        print(Fore.GREEN + "[INFO]: Requesting data from server")
        loop.run_until_complete(get_server_data())

        print(Fore.GREEN + "[INFO]: Robots detected:", ids)
        
        print(Fore.GREEN + "[INFO]: Requesting data from detected robots")
        loop.run_until_complete(get_robot_data(ids))

        # print(Fore.GREEN + "Processing...")

        print(Fore.GREEN + "[INFO]: Sending commands to detected robots")
        loop.run_until_complete(send_robot_commands(ids))

        print()

        # TODO: Close websocket connections
        if kill_now():
            loop.run_until_complete(stop_robots(robot_ids)) # Kill all robots, even if not visible
            break

        # Sleep until next control cycle
        time.sleep(0.1)
