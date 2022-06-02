#!/usr/bin/env python

import asyncio
import websockets
import json
import signal

MAX_SPEED = 500
ir_threshold = 300
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

async def test():
    async with websockets.connect("ws://pi-puck.local:5000") as websocket:

        while True:

            # Turn of LEDs and motors when killed
            if kill_now():
                message = {}
                message["set_leds_colour"] = "off"
                message["set_outer_leds"] = [0] * 8
                message["set_motor_speeds"] = {}
                message["set_motor_speeds"]["left"] = 0
                message["set_motor_speeds"]["right"] = 0
                await websocket.send(json.dumps(message))
                break

            # Construct request for data
            message = {}
            message["get_ir_reflected"] = True
            message["get_battery"] = True

            # Send request for data and wait for reply
            await websocket.send(json.dumps(message))
            reply_json = await websocket.recv()
            reply = json.loads(reply_json)

            ir_readings = reply["ir_reflected"]

            battery_charging = reply["battery"]["charging"]
            battery_voltage = reply["battery"]["voltage"]
            battery_percentage = reply["battery"]["percentage"]

            print(ir_readings)
            print("{}, {:.2f}V, {:.2f}%" .format("Charging" if battery_charging else "Discharging", battery_voltage, battery_percentage * 100))

            # Construct command message
            message = {}
            message["set_outer_leds"] = [0] * 8 # e-puck body LEDs off by default (no obstacles detected)

            left = right = MAX_SPEED / 2

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

            # Set Pi-puck RGB LEDs based on whether an obstacle has been detected
            if any(reading > ir_threshold for reading in ir_readings):
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

            message["set_motor_speeds"] = {}
            message["set_motor_speeds"]["left"] = left
            message["set_motor_speeds"]["right"] = right

            # Send command message
            await websocket.send(json.dumps(message))

            # Sleep until next control cycle
            await asyncio.sleep(0.1)

asyncio.run(test())