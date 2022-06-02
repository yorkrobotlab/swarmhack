#!/usr/bin/env python

import asyncio
import websockets
import json
import random

async def test():
    async with websockets.connect("ws://pi-puck.local:5000") as websocket:

        while True:
            data = {}
            data["led"] = {}
            data["led"]["num"] = random.randint(0, 2)
            data["led"]["r"] = random.choice([True, False])
            data["led"]["g"] = random.choice([True, False])
            data["led"]["b"] = random.choice([True, False])

            await websocket.send(json.dumps(data))
            await asyncio.sleep(0.5)

asyncio.run(test())