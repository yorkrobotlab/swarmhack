#!/usr/bin/env python3

from robots import robots, server_none, server_york
import asyncio, json, sys
import websockets
from websockets.sync.client import connect

server_address = server_york
server_port = 6000
robot_port = 6000

def stop_id(id):
    if id in robots:
        ip = robots[id]
        uri = f"ws://{ip}:{robot_port}"    
        with connect(uri) as websocket:
            message = {"set_leds_colour": "off", "set_motor_speeds": {}}
            message["set_motor_speeds"]["left"] = 0
            message["set_motor_speeds"]["right"] = 0
            websocket.send(json.dumps(message))
            print(f"Stop command sent to robot {id} <{ip}>")


if len(sys.argv) < 2:
    print(f"Usage {sys.argv[0]} id_to_stop")
    sys.exit(0)

try:
    if not int(sys.argv[1]) in robots:
        print(f"Unknown robot ID {sys.argv[1]}.")
        sys.exit(1)
except ValueError:
    print(f"{sys.argv[1]} is not a robot ID.")
    sys.exit(1)

stop_id(int(sys.argv[1]))
