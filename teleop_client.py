#!/usr/bin/env python3

# Based on ROS teleop_twist_keyboard: http://wiki.ros.org/teleop_twist_keyboard
# https://github.com/ros-teleop/teleop_twist_keyboard/blob/master/teleop_twist_keyboard.py

import websocket
import threading
import sys
import json


if sys.platform == 'win32':
    import msvcrt
else:
    import termios
    import tty


class PublishThread(threading.Thread):
    def __init__(self, ws):
        super(PublishThread, self).__init__()
        self.ws = ws
        self.key = ''
        self.condition = threading.Condition()
        self.done = False

        self.start()

    def update(self, key):
        self.condition.acquire()

        self.key = key

        # Notify publish thread that we have a new message
        self.condition.notify()
        self.condition.release()

    def stop(self):
        self.done = True
        self.update("teleop_stop") # Publish stop message when thread exits
        self.join()

    def run(self):
        while not self.done:
            self.condition.acquire()

            # Wait for new message notification from update()
            self.condition.wait()

            key = self.key

            self.condition.release()

            # Publish
            message = {"key": key}
            self.ws.send(json.dumps(message))


def getKey(settings):
    if sys.platform == 'win32':
        # getwch() returns a string on Windows
        key = msvcrt.getwch()
    else:
        tty.setraw(sys.stdin.fileno())
        # sys.stdin.read() returns a string on Linux
        key = sys.stdin.read(1)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


def saveTerminalSettings():
    if sys.platform == 'win32':
        return None
    return termios.tcgetattr(sys.stdin)


def restoreTerminalSettings(old_settings):
    if sys.platform == 'win32':
        return
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def on_message(ws, message):
    reply = json.loads(message)
    if "prompt" in reply:
        print(reply["prompt"], end='', flush=True)


def on_error(ws, error):
    print()
    print("Websocket error:", error)


def on_close(ws, close_status_code, close_msg):
    print()
    print("Closing websocket")


def on_open(ws):
    def run(*args):
        settings = saveTerminalSettings()
        pub_thread = PublishThread(ws)

        try:
            pub_thread.update("teleop_start")

            while True:
                key = getKey(settings)

                # Quit if Ctrl+C is pressed
                if key == '\x03':
                    break

                pub_thread.update(key)

        except Exception as e:
            print(e)

        finally:
            pub_thread.stop()
            ws.close()
            restoreTerminalSettings(settings)

    threading.Thread(target=run).start()


if __name__ == "__main__":

    host = "ws://localhost:7000/"

    webs = websocket.WebSocketApp(host,
                                  on_open=on_open,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close)
    webs.on_open = on_open
    webs.run_forever()
