from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .interfaces import ControllerFactory


REGISTRY_NAME = "robots.json"


@dataclass(frozen=True)
class RobotSpec:
    name: str
    display_name: str
    controller_factory: str
    instructions: str
    prepare_command: tuple[str, ...]
    system_site_packages: bool
    default_settings: dict[str, Any]
    setup_note: str

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "RobotSpec":
        required = {
            "display_name", "controller_factory", "instructions", "prepare_command",
            "system_site_packages", "default_settings", "setup_note",
        }
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Robot {name!r} is missing registry fields: {', '.join(sorted(missing))}")
        command = tuple(str(part) for part in data["prepare_command"])
        if not command:
            raise ValueError(f"Robot {name!r} must define a prepare_command")
        return cls(
            name=name,
            display_name=str(data["display_name"]),
            controller_factory=str(data["controller_factory"]),
            instructions=str(data["instructions"]),
            prepare_command=command,
            system_site_packages=bool(data["system_site_packages"]),
            default_settings=dict(data["default_settings"]),
            setup_note=str(data["setup_note"]),
        )

    def load_controller_factory(self) -> ControllerFactory:
        module_name, separator, attribute = self.controller_factory.partition(":")
        if not separator or not module_name or not attribute:
            raise ValueError(
                f"Invalid controller_factory for {self.name!r}: {self.controller_factory!r}"
            )
        factory = getattr(importlib.import_module(module_name), attribute)
        if not callable(factory):
            raise TypeError(f"Controller factory is not callable: {self.controller_factory}")
        return factory


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_robot_specs(root: Path | None = None) -> dict[str, RobotSpec]:
    root = root or project_root()
    path = root / REGISTRY_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{path} must contain a non-empty object")
    return {name: RobotSpec.from_dict(name, value) for name, value in data.items()}


def get_robot_spec(name: str, root: Path | None = None) -> RobotSpec:
    specs = load_robot_specs(root)
    try:
        return specs[name]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported robot {name!r}; registered robots: {', '.join(sorted(specs))}"
        ) from exc


def validate_robot_specs(root: Path | None = None) -> dict[str, RobotSpec]:
    root = (root or project_root()).resolve()
    specs = load_robot_specs(root)
    instruction_paths: set[Path] = set()
    for name, spec in specs.items():
        for label, configured in (
            ("instructions", spec.instructions),
            ("prepare_command", spec.prepare_command[0]),
        ):
            path = (root / configured).resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Robot {name!r} {label} escapes the repository: {configured}") from exc
            if not path.is_file():
                raise FileNotFoundError(f"Robot {name!r} {label} file is missing: {path}")
            if label == "instructions":
                if path in instruction_paths:
                    raise ValueError(f"Robot instruction module is shared by multiple robots: {path}")
                instruction_paths.add(path)
        spec.load_controller_factory()
    return specs
