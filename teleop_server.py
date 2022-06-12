#!/usr/bin/env python3

import asyncio
import websockets
import json
from enum import Enum

class State(Enum):
    START = 1
    SELECT = 2
    DRIVE = 3

async def send_message(websocket, message):
    await websocket.send(json.dumps({"prompt": message}))


async def handler(websocket):

    state = State.START
    robot_id = ""
    valid_robots = [1, 2, 10, 23]
    forwards = "w"
    backwards = "s"
    left = "a"
    right = "d"
    stop = " "
    release = "q"

    async for packet in websocket:
        message = json.loads(packet)
        print(message)

        if "key" in message:

            key = message["key"]

            if key == "teleop_start":
                state = State.START

            if state == State.START:
                await send_message(websocket, f"\r\nEnter robot ID ({valid_robots}), then press return: ")
                robot_id = ""
                state = State.SELECT

            elif state == State.SELECT:
                if key == "\r":
                    valid = False
                    try:
                        if int(robot_id) in valid_robots:
                            valid = True
                            await send_message(websocket, f"\r\nControlling robot ({release} to release): " + robot_id)
                            await send_message(websocket, f"\r\nControls: Forwards = {forwards}; Backwards = {backwards}; Left = {left}; Right = {right}; Stop = SPACE")
                            state = State.DRIVE
                    except ValueError:
                        pass

                    if not valid:
                        await send_message(websocket, "\r\nInvalid robot ID, try again: ")
                        robot_id = ""
                        state = State.SELECT

                else:
                    await send_message(websocket, key)
                    robot_id = robot_id + key

            elif state == State.DRIVE:
                if key == release:
                    await send_message(websocket, "\r\nReleasing control of robot: " + robot_id)
                    state = State.START
                elif key == forwards:
                    await send_message(websocket, "\r\nDriving forwards")
                elif key == backwards:
                    await send_message(websocket, "\r\nDriving backwards")
                elif key == left:
                    await send_message(websocket, "\r\nTurning left")
                elif key == right:
                    await send_message(websocket, "\r\nTurning right")
                elif key == stop:
                    await send_message(websocket, "\r\nStopping")
                else:
                    await send_message(websocket, "\r\nUnrecognised command")


if __name__ == "__main__":
    start_server = websockets.serve(ws_handler=handler, host=None, port=7000, ping_interval=None, ping_timeout=None)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server)
    loop.run_forever()