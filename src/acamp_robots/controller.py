"""Compatibility facade and registry-driven controller construction."""
from __future__ import annotations

from pathlib import Path

from .arm import ArmController
from .config import RobotConfig
from .errors import RobotError
from .hexapod import HexapodController
from .interfaces import RobotController
from .registry import get_robot_spec


def create_controller(config: RobotConfig, root: Path | None = None) -> RobotController:
    root = root or Path.cwd()
    factory = get_robot_spec(config.robot, root).load_controller_factory()
    controller = factory(config, root)
    missing = [name for name in ("status", "call", "stop") if not callable(getattr(controller, name, None))]
    if missing:
        raise TypeError(
            f"Controller for {config.robot!r} does not implement: {', '.join(missing)}"
        )
    return controller


__all__ = ["ArmController", "HexapodController", "RobotError", "create_controller"]
