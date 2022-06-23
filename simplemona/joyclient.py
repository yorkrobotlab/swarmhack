import websocket, sys, asyncio, time
from evdev import InputDevice, categorize, ecodes

if len(sys.argv < 3):
    print("Usage: " + sys.argv[0] + " <input device> <mona ip>")
    sys.exit(1)

device = sys.argv[1]
monaip = sys.argv[2]

dev = InputDevice(device) #'/dev/input/event1'
ws = websocket.create_connection("ws://" + monaip)

lasttransmit = 0
MIN_INTER_TRANSMIT_TIME = 0.1

async def helper(dev):
    async for ev in dev.async_read_loop():
        print(repr(ev))
        curtime = time.time()
        if curtime - lasttransmit > MIN_INTER_TRANSMIT_TIME:
            #leftw = 0
            #rightw = 0
            #ws.send('{"set_motor_speeds": {"left": "' + str(leftw) + '", "right": "' + str(rightw) + '"}}')
            lasttransmit = time.time()

asyncio.get_event_loop().run_until_complete(helper(dev))
