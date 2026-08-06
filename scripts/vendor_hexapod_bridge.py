#!/usr/bin/env python3
"""Small adapter around the separately installed Freenove server code."""
from __future__ import annotations

import argparse
import json
import os
import socketserver
import sys
import threading
import time
from pathlib import Path


class FreenoveDevice:
    """Stable API over Freenove's command-queue based Control class."""

    def __init__(self, control):
        self.control = control
        self.move_speed = 8
        self._lock = threading.RLock()
        self._stop_timer = None
        self._moving = False
        self._servo_power = None
        self._last_command = None

    def connect(self):
        if not self.control.condition_thread.is_alive():
            self.control.condition_thread.start()

    def servopower(self, on=True):
        with self._lock:
            if on:
                self.control.servo_power_disable.off()
            else:
                self.stop()
                self.control.servo_power_disable.on()
            self._servo_power = bool(on)

    def speed(self, tempo=8):
        with self._lock:
            self.move_speed = max(1, min(int(tempo), 20))
            return self.move_speed

    def _queue(self, *values):
        self.control.command_queue = [str(value) for value in values]
        self.control.timeout = time.time()
        self._last_command = self.control.command_queue.copy()

    def _cancel_stop_timer(self):
        if self._stop_timer is not None:
            self._stop_timer.cancel()
            self._stop_timer = None

    def move(self, gait=1, x=0, y=0, angle=0):
        # Values are restricted again by Freenove's condition monitor.
        with self._lock:
            self._cancel_stop_timer()
            self._moving = any(int(value) != 0 for value in (x, y, angle))
            self._queue("CMD_MOVE", int(gait), int(x), int(y), self.move_speed, int(angle))

    def stop(self):
        with self._lock:
            self._cancel_stop_timer()
            self._moving = False
            self._queue("CMD_MOVE", 1, 0, 0, self.move_speed, 0)

    def timed_move(self, duration, gait=1, x=0, y=0, angle=0):
        duration = float(duration)
        if not 0 < duration <= 5:
            raise ValueError("duration must be greater than 0 and at most 5 seconds")
        with self._lock:
            self.move(gait=gait, x=x, y=y, angle=angle)
            self._stop_timer = threading.Timer(duration, self.stop)
            self._stop_timer.daemon = True
            self._stop_timer.start()
        return {"accepted": True, "stop_after_seconds": duration}

    def balance(self, on=False):
        with self._lock:
            self._queue("CMD_BALANCE", 1 if on else 0)

    def position(self, x=0, y=0, z=0):
        with self._lock:
            self._queue("CMD_POSITION", int(x), int(y), int(z))

    def attitude(self, roll=0, pitch=0, yaw=0):
        with self._lock:
            self._queue("CMD_ATTITUDE", int(roll), int(pitch), int(yaw))

    def head_vertical(self, angle=90):
        with self._lock:
            self.control.servo.set_servo_angle(0, max(0, min(int(angle), 180)))

    def head_horizontal(self, angle=90):
        with self._lock:
            self.control.servo.set_servo_angle(1, max(0, min(int(angle), 180)))

    def status(self):
        return {
            "connected": self.control.condition_thread.is_alive(),
            "moving": self._moving,
            "servo_power": self._servo_power,
            "speed": self.move_speed,
            "last_command": self._last_command,
        }


def load_device(server_dir: Path):
    server_dir = server_dir.resolve()
    if not server_dir.is_dir():
        raise FileNotFoundError(f"Freenove server directory not found: {server_dir}")
    sys.path.insert(0, str(server_dir))
    # Freenove's vendor code reads point.txt relative to the process cwd.
    os.chdir(server_dir)
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
            args = request.get("args", [])
            kwargs = request.get("kwargs", {})
            try:
                if method == "ping":
                    result = {"pong": True}
                elif method == "shutdown":
                    if self.server.device is not None:
                        self.server.device.servopower(False)
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    result = {"shutting_down": True}
                elif method == "status":
                    if self.server.device is None:
                        result = {
                            "connected": False,
                            "initialized": False,
                            "moving": False,
                            "servo_power": False,
                        }
                    else:
                        result = self.server.device.status()
                        result["initialized"] = True
                    result["socket"] = self.server.server_address
                elif method == "servopower" and not bool(
                    kwargs.get("on", args[0] if args else True)
                ):
                    if self.server.device is not None:
                        self.server.device.servopower(False)
                    result = None
                else:
                    if self.server.device is None:
                        if method != "servopower":
                            raise RuntimeError(
                                "Hardware is not initialized. Call servopower true after checking the movement area."
                            )
                        with self.server.device_lock:
                            if self.server.device is None:
                                self.server.device = load_device(self.server.server_dir)
                    target = getattr(self.server.device, method)
                    if method.startswith("_") or not callable(target):
                        raise AttributeError(method)
                    result = target(*args, **kwargs)
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
        server.device = None
        server.device_lock = threading.Lock()
        server.server_dir = args.server_dir
        try:
            server.serve_forever()
        finally:
            if server.device is not None:
                server.device.stop()
                server.device.servopower(False)


if __name__ == "__main__":
    main()
