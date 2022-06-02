#!/usr/bin/env python

import asyncio
import websockets
import json
from pipuck.pipuck import PiPuck

pipuck = PiPuck()

async def handler(websocket):
    async for message in websocket:
        print(message)

        data = json.loads(message)
        print(data)

        if "led" in data:
            led = data["led"]
            num = led["num"]
            r = led["r"]
            g = led["g"]
            b = led["b"]
            print("Setting LED", num, "- R:", r, ", G:", g, ", B:", b)
            pipuck.set_led_rgb(num, r, g, b)

if __name__ == "__main__":
    start_server = websockets.serve(ws_handler=handler, host=None, port=5000)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()