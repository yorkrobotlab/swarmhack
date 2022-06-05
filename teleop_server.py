import asyncio
import websockets
import json


async def handler(websocket):
    async for packet in websocket:
        message = json.loads(packet)
        print(message)


if __name__ == "__main__":
    start_server = websockets.serve(ws_handler=handler, host=None, port=6000, ping_interval=None, ping_timeout=None)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_server)
    loop.run_forever()