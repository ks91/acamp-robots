from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path
from typing import Any

from .config import RobotConfig


class RobotError(RuntimeError):
    pass


class ArmController:
    """Loads the vendor-provided Arm_Lib.py without redistributing it."""

    def __init__(self, library_path: Path):
        if not library_path.is_file():
            raise RobotError(f"Arm_Lib.py が見つかりません: {library_path}")
        spec = importlib.util.spec_from_file_location("acamp_vendor_arm_lib", library_path)
        if spec is None or spec.loader is None:
            raise RobotError(f"Arm_Lib.py を読み込めません: {library_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.device = module.Arm_Device()

    def move_joints(self, joints: list[int], duration_ms: int = 1000) -> Any:
        if len(joints) != 6:
            raise ValueError("joints は6個の角度を指定してください")
        return self.device.Arm_serial_servo_write6_array(joints, duration_ms)

    def stop(self) -> Any:
        return self.device.Arm_serial_set_torque(0)


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
                client.settimeout(self.timeout)
                client.connect(self.socket_path)
                client.sendall(json.dumps(request).encode("utf-8") + b"\n")
                response = self._receive_line(client)
        except OSError as exc:
            raise RobotError(f"ヘクサポッド RPC に接続できません: {exc}") from exc
        message = json.loads(response.decode("utf-8"))
        if not message.get("ok"):
            raise RobotError(message.get("error", "ヘクサポッド RPC エラー"))
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
            raise RobotError("ヘクサポッド RPC から応答がありません")
        return bytes(data).split(b"\n", 1)[0]

    def status(self) -> Any:
        return self.call("status")

    def stop(self) -> Any:
        return self.call("stop")


def create_controller(config: RobotConfig, root: Path | None = None) -> ArmController | HexapodController:
    root = root or Path.cwd()
    if config.robot == "arm":
        path = Path(config.arm_lib)
        return ArmController(path if path.is_absolute() else root / path)
    return HexapodController(config.hexapod_socket)

