#!/usr/bin/env python3

import sys, asyncio, time, glob, os
import websockets
from evdev import InputDevice, categorize, ecodes

if len(sys.argv) < 3:
    print("Usage: " + sys.argv[0] + " <input device> <mona hostname>")
    print("Detected Logitech F710s:")
    for file in list(glob.glob('/dev/input/event*')):
        dev = InputDevice(file)
        if dev.name.find("F710") != -1:
            print("\t" + file)
    sys.exit(1)

devicepath = sys.argv[1] #i.e. '/dev/input/event2'
monaurl = "ws://" + sys.argv[2] + "/ws"
dev = InputDevice(devicepath)
print("Device at " + devicepath + " is: " + dev.name)


lasttransmit = 0
leftw, rightw = 0, 0
joyx, joyy = 0, 0
MIN_INTER_TRANSMIT_TIME = 0.01


async def helper(dev):
    global joyx, joyy, lasttransmit

    async for ws in websockets.connect(monaurl):
        try:
            print("Connected to Mona at " + monaurl)

            async for ev in dev.async_read_loop():
                if ev.type == ecodes.EV_ABS:
                    #print(repr(ev))

                    #If controlling using DPad...
                    if ev.code == 0 or ev.code == 1:
                        leftw, rightw = 0, 0
                        if ev.code == 1: #Forward backward on DPad
                            if ev.value < -30000: #Forward
                                leftw, rightw = 800, 800
                            elif ev.value > 30000: #Backward
                                leftw, rightw = -255, -255
                        elif ev.code == 0: #Left right on DPad
                            if ev.value < -30000: #Left
                                leftw, rightw = -255, 255
                            elif ev.value > 30000: #Right
                                leftw, rightw = 255, -255
                        #sendWheelSpeeds(leftw, rightw)
                        if time.time() - lasttransmit > MIN_INTER_TRANSMIT_TIME:
                            msg = '{"set_motor_speeds": {"left": "' + str(leftw) + '", "right": "' + str(rightw) + '"}}'
                            print("Sending: " + msg)
                            await ws.send(msg)
                            lasttransmit = time.time()

                    #If controlling using right stick...
                    if ev.code == 3 or ev.code == 4:
                        if ev.code == 4: #Analogue fw -32768, bw 32768
                            joyy = ev.value
                        elif ev.code == 3: #Analogue left -32768, right 32768
                            joyx = ev.value

                        leftw, rightw = getWheelsFromStick(joyx, joyy)

                        if time.time() - lasttransmit > MIN_INTER_TRANSMIT_TIME:
                            msg = '{"set_motor_speeds": {"left": "' + str(leftw) + '", "right": "' + str(rightw) + '"}}'
                            print("Wheels to L:" + str(leftw) + " R:" + str(rightw))
                            await ws.send(msg)
                            lasttransmit = time.time()
        except websockets.ConnectionClosed:
            continue


async def sendWheelSpeeds(l, r):
    global lasttransmit
    if time.time() - lasttransmit > MIN_INTER_TRANSMIT_TIME:
        msg = '{"set_motor_speeds": {"left": "' + str(l) + '", "right": "' + str(r) + '"}}'
        print("Sending: " + msg)
        await ws.send(msg)
        lasttransmit = time.time()

def getWheelsFromStick(joyx, joyy):
    xclamp, yclamp = joyx, joyy
    if xclamp > 30000: xclamp == 30000
    if yclamp > 30000: yclamp == 30000
    if xclamp < -30000: xclamp == -30000
    if yclamp < -30000: yclamp == -30000
    if abs(xclamp) < 300: xclamp = 0
    if abs(yclamp) < 300: yclamp = 0
    fw = 250*(yclamp / -30000)
    leftw, rightw = fw, fw
    if(xclamp > 0):
        leftw = leftw - (-xclamp/30000*500)
        rightw = rightw - ((-xclamp)/(-30000)*500)
    if(xclamp < 0):
        leftw = leftw - (xclamp/-30000*500)
        rightw = rightw - ((xclamp)/(30000)*500)
    leftw = round(leftw)
    rightw = round(rightw)
    if abs(leftw) < 65: leftw = 0
    if abs(rightw) < 65: rightw = 0
    return (leftw, rightw)

asyncio.get_event_loop().run_until_complete(helper(dev))
