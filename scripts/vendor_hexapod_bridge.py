#!/usr/bin/env python3
"""Small adapter around the separately installed Freenove server code."""
from __future__ import annotations

import argparse
import json
import os
import socketserver
import sys
import time
from pathlib import Path


class FreenoveDevice:
    """Stable API over Freenove's command-queue based Control class."""

    def __init__(self, control):
        self.control = control
        self.move_speed = 8

    def connect(self):
        if not self.control.condition_thread.is_alive():
            self.control.condition_thread.start()

    def servopower(self, on=True):
        if on:
            self.control.servo_power_disable.off()
        else:
            self.control.servo_power_disable.on()

    def speed(self, tempo=8):
        self.move_speed = max(1, min(int(tempo), 20))
        return self.move_speed

    def _queue(self, *values):
        self.control.command_queue = [str(value) for value in values]
        self.control.timeout = time.time()

    def move(self, gait=1, x=0, y=0, angle=0):
        # Values are restricted again by Freenove's condition monitor.
        self._queue("CMD_MOVE", int(gait), int(x), int(y), self.move_speed, int(angle))

    def stop(self):
        self.move(gait=1, x=0, y=0, angle=0)

    def balance(self, on=False):
        self._queue("CMD_BALANCE", 1 if on else 0)

    def position(self, x=0, y=0, z=0):
        self._queue("CMD_POSITION", int(x), int(y), int(z))

    def attitude(self, roll=0, pitch=0, yaw=0):
        self._queue("CMD_ATTITUDE", int(roll), int(pitch), int(yaw))

    def head_vertical(self, angle=90):
        self.control.servo.set_servo_angle(0, max(0, min(int(angle), 180)))

    def head_horizontal(self, angle=90):
        self.control.servo.set_servo_angle(1, max(0, min(int(angle), 180)))


def load_device(server_dir: Path):
    sys.path.insert(0, str(server_dir))
    from control import Control  # type: ignore

    device = FreenoveDevice(Control())
    device.connect()
    return device


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for raw in self.rfile:
            request = json.loads(raw)
            request_id = request.get("id")
            method = request.get("method")
            try:
                if method == "status":
                    result = {"connected": True, "socket": self.server.server_address}
                else:
                    target = getattr(self.server.device, method)
                    if method.startswith("_") or not callable(target):
                        raise AttributeError(method)
                    result = target(*request.get("args", []), **request.get("kwargs", {}))
                response = {"id": request_id, "ok": True, "result": result}
            except Exception as exc:
                response = {"id": request_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self.wfile.write(json.dumps(response, default=repr).encode() + b"\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--server-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.path.exists(args.socket):
        os.unlink(args.socket)
    with socketserver.ThreadingUnixStreamServer(args.socket, Handler) as server:
        server.device = load_device(args.server_dir)
        server.serve_forever()


if __name__ == "__main__":
    main()
