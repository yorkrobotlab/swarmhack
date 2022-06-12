#!/usr/bin/env python

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

        if "get_ir_reflected" in message:
            reply["ir_reflected"] = pipuck.epuck.ir_reflected
            send_reply = True
        
        if "get_ir_ambient" in message:
            reply["ir_ambient"] = pipuck.epuck.ir_ambient
            send_reply = True

        if "get_battery" in message:
            charging, voltage, percentage = pipuck.get_battery_state("epuck")
            reply["battery"] = {}
            reply["battery"]["charging"] = charging
            reply["battery"]["voltage"] = voltage
            reply["battery"]["percentage"] = percentage
            send_reply = True
        
        # Send reply, if requested
        if send_reply:
            await websocket.send(json.dumps(reply))

        # Process any commands received
        if "set_outer_leds" in message:
            outer_leds = message["set_outer_leds"]
            pipuck.epuck.set_outer_leds(outer_leds[0],
                                        outer_leds[1],
                                        outer_leds[2],
                                        outer_leds[3],
                                        outer_leds[4],
                                        outer_leds[5],
                                        outer_leds[6],
                                        outer_leds[7])

        if "set_leds_colour" in message:
            pipuck.set_leds_colour(message["set_leds_colour"])

        if "set_motor_speeds" in message:
            pipuck.epuck.set_motor_speeds(message["set_motor_speeds"]["left"],
                                          message["set_motor_speeds"]["right"])

if __name__ == "__main__":
    start_server = websockets.serve(ws_handler=handler, host=None, port=5000)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()