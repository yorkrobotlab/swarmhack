#!/usr/bin/env python3

import asyncio
import websockets
import json
from pipuck.pipuck import PiPuck

pipuck = PiPuck(epuck_version=1)
pipuck.epuck.enable_ir_sensors(True)


async def handler(websocket):
    async for packet in websocket:
        message = json.loads(packet)

        # Process any requests received
        reply = {}
        send_reply = False

        if "check_awake" in message:
            reply["awake"] = True
            send_reply = True

        if "get_ir" in message:
            reply["ir"] = pipuck.epuck.ir_reflected
            send_reply = True

        if "get_battery" in message:
            charging, voltage, percentage = pipuck.get_battery_state("epuck")
            reply["battery"] = {}
            reply["battery"]["voltage"] = voltage
            reply["battery"]["percentage"] = int(percentage * 100)
            send_reply = True

        # Send reply, if requested
        if send_reply:
            await websocket.send(json.dumps(reply))

        if "set_leds_colour" in message:
            try:
                pipuck.set_leds_colour(message["set_leds_colour"])
            except (KeyError, ValueError):
                pass

        if "set_motor_speeds" in message:
            try:
                left_in = int(message["set_motor_speeds"]["left"])
                right_in = int(message["set_motor_speeds"]["right"])
                left_clamped = max(min(left_in, 100), -100)
                right_clamped = max(min(right_in, 100), -100)
                left_scaled = left_clamped * 5
                right_scaled = right_clamped * 5
                pipuck.epuck.set_motor_speeds(left_scaled, right_scaled)
            except (KeyError, ValueError):
                pass


if __name__ == "__main__":
    start_server = websockets.serve(ws_handler=handler, host=None, port=80)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
