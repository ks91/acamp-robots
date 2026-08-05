from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_NAME = ".acamp-robot.json"
ROBOT_TYPES = ("arm", "hexapod")


@dataclass(frozen=True)
class RobotConfig:
    robot: str
    arm_lib: str = "hardware/Arm_Lib.py"
    hexapod_socket: str = "/tmp/acamp-hexapod.sock"
    hexapod_server_dir: str = "hardware/freenove/Code/Server"

    def __post_init__(self) -> None:
        if self.robot not in ROBOT_TYPES:
            raise ValueError(f"robot must be one of: {', '.join(ROBOT_TYPES)}")


def save_config(config: RobotConfig, root: Path) -> Path:
    path = root / CONFIG_NAME
    path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
    return path


def load_config(root: Path | None = None) -> RobotConfig:
    root = root or Path.cwd()
    path = root / CONFIG_NAME
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. Run ./scripts/setup.sh --robot arm or hexapod first."
        )
    return RobotConfig(**json.loads(path.read_text(encoding="utf-8")))
