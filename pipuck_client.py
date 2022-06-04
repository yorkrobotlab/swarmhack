#!/usr/bin/env python

import asyncio
import websockets
import json
import signal
import time
import random
from itertools import chain

import colorama
from colorama import Fore

colorama.init(autoreset = True)

MAX_SPEED = 500
ir_threshold = 300
BAT_LOW_VOLTAGE = 3.6
weights_left = [-10, -10, -5, 0, 0, 5, 10, 10]
weights_right = [-1 * x for x in weights_left]

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

server_port = 6000
robot_port = 5000

connections = {}

tasks = []

ids = []
ir_readings = []
battery_charging = False
battery_voltage = 0
battery_percentage = 0

async def connect_to_robots(ids):
    loop = asyncio.get_event_loop()

    for id in ids:
        uri = "ws://pi-puck-" + str(id) + ".local:" + str(robot_port)
        connection = websockets.connect(uri)

        print("Checking robot:", id)

        awake = False

        try:
            async with connection as websocket:

                message = {}
                message["check_awake"] = True

                # Send request for data and wait for reply
                await websocket.send(json.dumps(message))
                reply_json = await websocket.recv()
                reply = json.loads(reply_json)
                print(reply)
                awake = reply["awake"]

        except Exception as e:
            print(f"{type(e).__name__}: {e}")

        if(awake):
            print("Robot is awake:", id)
            connections[id] = connection # Add to set if successful
        else:
            print("Robot did not respond:", id)


async def get_robot_data(ids):
    await message_robots(ids, subscribe_one)

async def send_robot_commands(ids):
    await message_robots(ids, publish_one)

async def stop_robots(ids):
    await message_robots(ids, stop_robot)

# https://stackoverflow.com/questions/49858021/listen-to-multiple-socket-with-websockets-and-asyncio
async def message_robots(ids, function):
    loop = asyncio.get_event_loop()

    for id, connection in connections.items():
        if id in ids:
            tasks.append(loop.create_task(function(connection)))
    
    await asyncio.gather(*tasks)

async def stop_robot(connection):
    try:
        async with connection as websocket:

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

async def subscribe_one(connection):
    try:
        async with connection as websocket:

            message = {}
            message["get_ir_reflected"] = True
            message["get_battery"] = True

            # Send request for data and wait for reply
            await websocket.send(json.dumps(message))
            reply_json = await websocket.recv()
            reply = json.loads(reply_json)
            print(reply)

            global ir_readings
            global battery_charging
            global battery_voltage
            global battery_percentage

            ir_readings = reply["ir_reflected"]

            battery_charging = reply["battery"]["charging"]
            battery_voltage = reply["battery"]["voltage"]
            battery_percentage = reply["battery"]["percentage"]

            print(ir_readings)
            print("{}, {:.2f}V, {:.2f}%" .format("Charging" if battery_charging else "Discharging", battery_voltage, battery_percentage * 100))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")

async def get_server_data(uri):
    try:
        async with websockets.connect(uri) as websocket:

            global ids
            message = {}
            message["get_ids"] = True
            
            # Send request for data and wait for reply
            await websocket.send(json.dumps(message))
            reply_json = await websocket.recv()
            reply = json.loads(reply_json)
            
            ids = list(chain.from_iterable(reply["ids"]))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")

async def publish_one(connection):
    try:
        async with connection as websocket:

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

            left = right = MAX_SPEED / 2

            print("IR readings:", ir_readings)

            for i, reading in enumerate(ir_readings):
                if reading > ir_threshold:
                    # Set wheel speeds to avoid detected obstacles
                    left += weights_left[i] * reading
                    right += weights_right[i] * reading

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
            if battery_voltage < BAT_LOW_VOLTAGE:
                message["set_leds_colour"] = "red"
            else:
                message["set_leds_colour"] = "green"

            # Clamp wheel speeds between min/max values
            if left > MAX_SPEED:
                left = MAX_SPEED
            elif left < -MAX_SPEED:
                left = -MAX_SPEED

            if right > MAX_SPEED:
                right = MAX_SPEED
            elif right < -MAX_SPEED:
                right = -MAX_SPEED

            left = right = 0

            message["set_motor_speeds"] = {}
            message["set_motor_speeds"]["left"] = left
            message["set_motor_speeds"]["right"] = right

            # Send command message
            await websocket.send(json.dumps(message))

    except Exception as e:
        print(f"{type(e).__name__}: {e}")

# TODO: Keep websocket connections open between subscribe/publish cycles?
# while True:

loop = asyncio.get_event_loop()

robot_ids = [1, 2]
loop.run_until_complete(connect_to_robots(robot_ids))

while True:

    # TODO: Keep websocket connection to server open permanently as well
    print(Fore.GREEN + "Requesting data from server")
    loop.run_until_complete(get_server_data("ws://localhost:6000"))

    print(Fore.GREEN + "Robots detected:", ids)
    
    print(Fore.GREEN + "Requesting data from detected robots")
    loop.run_until_complete(get_robot_data(ids))

    # print(Fore.GREEN + "Processing...")

    print(Fore.GREEN + "Sending commands to detected robots")
    loop.run_until_complete(send_robot_commands(ids))

    print()

    # TODO: Close websocket connections
    if kill_now():
        loop.run_until_complete(stop_robots(robot_ids)) # Kill all robots, even if not visible
        break

    # Sleep until next control cycle
    # time.sleep(0.1)
    