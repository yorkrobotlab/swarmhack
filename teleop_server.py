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

    async for packet in websocket:
        message = json.loads(packet)
        print(message)

        if "key" in message:

            key = message["key"]

            if key == "teleop_start":
                state = State.START

            if state == State.START:
                # await send_message(websocket, {"prompt": "Type robot ID, followed by hash"})
                await send_message(websocket, "Enter robot ID, then press return: ")
                robot_id = ""
                state = State.SELECT

            elif state == State.SELECT:
                if key == "\r":
                    await send_message(websocket, "\r\nSelected robot: " + robot_id)
                    state = State.DRIVE
                else:
                    await send_message(websocket, key)
                    robot_id = robot_id + key
                    print(robot_id)

            elif state == State.DRIVE:
                await send_message(websocket, "\r\nDriving")


if __name__ == "__main__":
    start_server = websockets.serve(ws_handler=handler, host=None, port=6000, ping_interval=None, ping_timeout=None)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server)
    loop.run_forever()