#!/usr/bin/env python

import asyncio
import websockets
import json
import signal
import time
import random
from itertools import chain
import sys

import colorama
from colorama import Fore

colorama.init(autoreset = True)

# Handle Ctrl+C termination

# https://stackoverflow.com/questions/2148888/python-trap-all-signals
SIGNALS_TO_NAMES_DICT = dict((getattr(signal, n), n) \
    for n in dir(signal) if n.startswith('SIG') and '_' not in n )

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

server_address = "localhost"
server_port = 6000
robot_port = 5000

server_connection = None
robots = {}
ids = []

class Robot:

    BAT_LOW_VOLTAGE = 3.6
    MAX_SPEED = 500
    ir_threshold = 300
    weights_left = [-10, -10, -5, 0, 0, 5, 10, 10]
    weights_right = [-1 * x for x in weights_left]

    def __init__(self, id, connection):
        self.id = id
        self.connection = connection

        self.ir_readings = []
        self.battery_charging = False
        self.battery_voltage = 0
        self.battery_percentage = 0

async def connect_to_server():
    loop = asyncio.get_event_loop()

    uri = "ws://" + server_address + ":" + str(server_port)
    connection = websockets.connect(uri)

    print("Opening connection to server: " + uri)

    awake = await check_awake(connection)

    if(awake):
        print("Server is awake")
        global server_connection
        server_connection = connection
    else:
        print("Server did not respond")

async def connect_to_robots(ids):
    loop = asyncio.get_event_loop()

    for id in ids:
        uri = "ws://pi-puck-" + str(id) + ".local:" + str(robot_port)
        connection = websockets.connect(uri)

        print("Opening connection to robot:", uri)

        awake = await check_awake(connection)

        if(awake):
            print(f"Robot {id} is awake")
            robots[id] = Robot(id, connection)
        else:
            print(f"Robot {id} did not respond")

async def check_awake(connection):
    awake = False

    try:
        async with connection as websocket:

            message = {}
            message["check_awake"] = True

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

    for id, robot in robots.items():
        if id in ids:
            tasks.append(loop.create_task(function(robot)))
    
    await asyncio.gather(*tasks)

async def get_server_data():
    try:
        async with server_connection as websocket:

            global ids
            message = {}
            message["get_ids"] = True
            
            # Send request for data and wait for reply
            await websocket.send(json.dumps(message))
            reply_json = await websocket.recv()
            reply = json.loads(reply_json)
            
            # TODO: Get server to return IDs in a more sensible format
            ids = list(chain.from_iterable(reply["ids"]))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")

async def stop_robot(robot):
    try:
        async with robot.connection as websocket:

            # Turn of LEDs and motors when killed
            message = {}
            message["set_leds_colour"] = "off"
            message["set_outer_leds"] = [0] * 8
            message["set_motor_speeds"] = {}
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

            message = {}
            message["get_ir_reflected"] = True
            message["get_battery"] = True

            # Send request for data and wait for reply
            await websocket.send(json.dumps(message))
            reply_json = await websocket.recv()
            reply = json.loads(reply_json)
            print(reply)

            robot.ir_readings = reply["ir_reflected"]

            robot.battery_charging = reply["battery"]["charging"]
            robot.battery_voltage = reply["battery"]["voltage"]
            robot.battery_percentage = reply["battery"]["percentage"]

            print(robot.ir_readings)
            print("{}, {:.2f}V, {:.2f}%" .format("Charging" if robot.battery_charging else "Discharging",
                                                  robot.battery_voltage,
                                                  robot.battery_percentage * 100))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")

async def send_commands(robot):
    try:
        async with robot.connection as websocket:

            # Turn of LEDs and motors when killed
            if kill_now():
                message = {}
                message["set_leds_colour"] = "off"
                message["set_outer_leds"] = [0] * 8
                message["set_motor_speeds"] = {}
                message["set_motor_speeds"]["left"] = 0
                message["set_motor_speeds"]["right"] = 0
                await websocket.send(json.dumps(message))

            # message = {}
            # message["set_leds_colour"] = random.choice(['red', 'yellow', 'green', 'cyan', 'blue', 'magenta'])

            # Construct command message
            message = {}
            message["set_outer_leds"] = [0] * 8 # e-puck body LEDs off by default (no obstacles detected)

            left = right = robot.MAX_SPEED / 2

            print("IR readings:", robot.ir_readings)

            for i, reading in enumerate(robot.ir_readings):
                if reading > robot.ir_threshold:
                    # Set wheel speeds to avoid detected obstacles
                    left += robot.weights_left[i] * reading
                    right += robot.weights_right[i] * reading

                    # Illuminate e-puck body LEDs based on which IR sensors have detected an obstacle
                    if i in [0, 7]:
                        message["set_outer_leds"][0] = 1
                    elif i == 1:
                        message["set_outer_leds"][1] = 1
                    elif i == 2:
                        message["set_outer_leds"][2] = 1
                    elif i == 3:
                        message["set_outer_leds"][3] = 1
                        message["set_outer_leds"][4] = 1
                    elif i == 4:
                        message["set_outer_leds"][4] = 1
                        message["set_outer_leds"][5] = 1
                    elif i == 5:
                        message["set_outer_leds"][6] = 1
                    elif i == 6:
                        message["set_outer_leds"][7] = 1

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

            left = right = 0

            message["set_motor_speeds"] = {}
            message["set_motor_speeds"]["left"] = left
            message["set_motor_speeds"]["right"] = right

            # Send command message
            await websocket.send(json.dumps(message))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    loop.run_until_complete(connect_to_server())

    if server_connection is None:
        sys.exit(1)

    robot_ids = [1, 2] # Specify robots to work with

    print(Fore.GREEN + "[INFO]: Connecting to robots")
    loop.run_until_complete(connect_to_robots(robot_ids))

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
        # time.sleep(0.1)
        