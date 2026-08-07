from __future__ import annotations

import argparse
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True

    @property
    def exit_failure(self) -> bool:
        return self.required and not self.ok


def _module_available(name: str) -> bool:
    if name == "cv2.aruco":
        try:
            import cv2
        except ImportError:
            return False
        return hasattr(cv2, "aruco")
    return importlib.util.find_spec(name) is not None


def inspect_research_environment(
    root: Path | str,
    *,
    module_available: Callable[[str], bool] = _module_available,
    strict_vision: bool = False,
) -> list[Check]:
    root = Path(root).resolve()
    config_path = root / ".acamp-robot.json"
    configured = False
    detail = "missing .acamp-robot.json"
    if config_path.is_file():
        try:
            robot = json.loads(config_path.read_text(encoding="utf-8")).get("robot")
            configured = bool(robot)
            detail = f"configured robot: {robot}" if configured else "missing robot value"
        except (OSError, ValueError):
            detail = "malformed .acamp-robot.json"
    return [
        Check("robot configuration", configured, detail),
        Check("virtual environment", (root / ".venv").is_dir(), str(root / ".venv")),
        Check(
            "local projects directory",
            (root / "projects").is_dir(),
            str(root / "projects"),
        ),
        Check("NumPy", module_available("numpy"), "Python module numpy", required=strict_vision),
        Check("OpenCV", module_available("cv2"), "Python module cv2", required=strict_vision),
        Check(
            "OpenCV marker backend",
            module_available("cv2.aruco"),
            "cv2.aruco with AprilTag dictionaries",
            required=strict_vision,
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the local research environment")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--strict-vision",
        action="store_true",
        help="require NumPy, OpenCV, and the AprilTag-capable aruco module",
    )
    args = parser.parse_args(argv)
    checks = inspect_research_environment(args.root, strict_vision=args.strict_vision)
    for check in checks:
        label = "OK" if check.ok else ("FAIL" if check.required else "OPTIONAL")
        print(f"[{label}] {check.name}: {check.detail}")
    return 1 if any(check.exit_failure for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
