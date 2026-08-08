from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from .config import RobotConfig
from .errors import RobotError
from .usb_sensors import environment_read, microphone_level


class HexapodController:
    """Newline-delimited JSON client for the local hardware RPC bridge."""

    def __init__(self, socket_path: str, timeout: float = 5.0):
        self.socket_path = socket_path
        self.timeout = timeout
        self._request_id = 0

    def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        self._request_id += 1
        request = {
            "id": self._request_id,
            "method": method,
            "args": list(args),
            "kwargs": kwargs,
        }
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                minimum_timeouts = {"camera_capture": 15.0, "turn_by": 35.0}
                request_timeout = max(self.timeout, minimum_timeouts.get(method, 0.0))
                client.settimeout(request_timeout)
                client.connect(self.socket_path)
                client.sendall(json.dumps(request).encode("utf-8") + b"\n")
                response = self._receive_line(client)
        except OSError as exc:
            raise RobotError(f"Could not connect to the hexapod RPC bridge: {exc}") from exc
        message = json.loads(response.decode("utf-8"))
        if not message.get("ok"):
            raise RobotError(message.get("error", "Hexapod RPC error"))
        return message.get("result")

    @staticmethod
    def _receive_line(client: socket.socket) -> bytes:
        data = bytearray()
        while b"\n" not in data:
            chunk = client.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
        if not data:
            raise RobotError("The hexapod RPC bridge returned no response")
        return bytes(data).split(b"\n", 1)[0]

    def status(self) -> Any:
        return self.call("status")

    def stop(self) -> Any:
        return self.call("stop")

    def environment_read(self, port: str | None = None) -> dict[str, Any]:
        return environment_read(port)

    def microphone_level(
        self, duration_seconds: float = 1.0, device: str | None = None
    ) -> dict[str, Any]:
        return microphone_level(duration_seconds, device)


def create_controller(config: RobotConfig, root: Path) -> HexapodController:
    del root
    return HexapodController(config.get("hexapod_socket", "/tmp/acamp-hexapod.sock"))
