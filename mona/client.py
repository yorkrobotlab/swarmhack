#!/usr/bin/env python3

import websocket
import _thread
import time

def on_message(ws, message):
    print(message)

def on_error(ws, error):
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    print("Opened connection")

if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp("ws://144.32.165.239/", on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.run_forever()
    print("hello")
