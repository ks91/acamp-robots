from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .registry import get_robot_spec, load_robot_specs

CONFIG_NAME = ".acamp-robot.json"


@dataclass(frozen=True)
class RobotConfig:
    robot: str
    settings: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", dict(self.settings))

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)


def default_config(robot: str, root: Path | None = None, **overrides: Any) -> RobotConfig:
    spec = get_robot_spec(robot, root)
    return RobotConfig(robot=robot, settings=spec.default_settings | overrides)


def save_config(config: RobotConfig, root: Path) -> Path:
    path = root / CONFIG_NAME
    data = {"robot": config.robot, "settings": config.settings}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def load_config(root: Path | None = None) -> RobotConfig:
    root = root or Path.cwd()
    path = root / CONFIG_NAME
    if not path.exists():
        registered = "|".join(sorted(load_robot_specs(root)))
        raise FileNotFoundError(
            f"{path} does not exist. Run ./scripts/setup.sh --robot {registered} first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    robot = data.pop("robot")
    settings = data.pop("settings", {})
    # Read checkouts configured by versions before the generic settings schema.
    settings = dict(data) | dict(settings)
    defaults = get_robot_spec(robot, root).default_settings
    return RobotConfig(robot=robot, settings=defaults | settings)
