#!/usr/bin/env python3
"""Registry-driven setup and session preparation for robot plugins."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acamp_robots.config import default_config, load_config, save_config
from acamp_robots.registry import get_robot_spec, load_robot_specs, validate_robot_specs


def parse_setting(value: str) -> tuple[str, object]:
    key, separator, setting = value.partition("=")
    if not separator or not key:
        raise argparse.ArgumentTypeError("settings must use KEY=VALUE")
    try:
        parsed = json.loads(setting)
    except json.JSONDecodeError:
        parsed = setting
    return key, parsed


def resolve_prepare_command(parts: tuple[str, ...]) -> list[str]:
    executable = Path(parts[0])
    if not executable.is_absolute():
        executable = (ROOT / executable).resolve()
        try:
            executable.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise ValueError("prepare_command must stay inside the repository") from exc
    if not executable.is_file():
        raise FileNotFoundError(f"Robot preparation executable not found: {executable}")
    return [str(executable), *parts[1:]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--separator", default="\n")

    configure = subparsers.add_parser("configure")
    configure.add_argument("--robot", required=True)
    configure.add_argument("--set", action="append", default=[], type=parse_setting)

    field = subparsers.add_parser("field")
    field.add_argument("robot")
    field.add_argument("name", choices=("system_site_packages", "setup_note", "instructions"))

    subparsers.add_parser("prepare")
    args = parser.parse_args(argv)
    validate_robot_specs(ROOT)

    if args.command == "list":
        print(args.separator.join(sorted(load_robot_specs(ROOT))))
        return 0
    if args.command == "configure":
        config = default_config(args.robot, ROOT, **dict(args.set))
        path = save_config(config, ROOT)
        print(f"Wrote configuration: {path}")
        return 0
    if args.command == "field":
        value = getattr(get_robot_spec(args.robot, ROOT), args.name)
        print(str(value).lower() if isinstance(value, bool) else value)
        return 0

    config = load_config(ROOT)
    spec = get_robot_spec(config.robot, ROOT)
    subprocess.run(resolve_prepare_command(spec.prepare_command), cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
