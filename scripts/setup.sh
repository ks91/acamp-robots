#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROBOT=""
HEXAPOD_SERVER_DIR="hardware/freenove/Code/Server"

usage() {
  echo "Usage: ./scripts/setup.sh --robot arm|hexapod [--hexapod-server-dir PATH]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --robot) ROBOT="${2:-}"; shift 2 ;;
    --hexapod-server-dir) HEXAPOD_SERVER_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$ROBOT" != "arm" && "$ROBOT" != "hexapod" ]]; then
  usage >&2
  exit 2
fi

python3 - "$ROOT_DIR" "$ROBOT" "$HEXAPOD_SERVER_DIR" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "src"))
from acamp_robots.config import RobotConfig, save_config

path = save_config(RobotConfig(robot=sys.argv[2], hexapod_server_dir=sys.argv[3]), root)
print(f"Wrote configuration: {path}")
PY

if [[ "$ROBOT" == "arm" ]]; then
  # Arm_Lib.py and OpenCV are normally supplied by the Raspberry Pi image as
  # system packages and are intentionally not redistributed by this project.
  python3 -m venv --system-site-packages "$ROOT_DIR/.venv"
else
  python3 -m venv "$ROOT_DIR/.venv"
fi
"$ROOT_DIR/.venv/bin/python" -m pip install -e "$ROOT_DIR"

if [[ "$ROBOT" == "arm" ]]; then
  echo "Selected DOFBOT. Follow the README to install hardware/Arm_Lib.py."
else
  echo "Selected Freenove Hexapod. Follow the README to install the vendor server."
fi
