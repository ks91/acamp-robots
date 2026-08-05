#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROBOT=""

usage() {
  echo "使い方: ./scripts/setup.sh --robot arm|hexapod"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --robot) ROBOT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "不明な引数: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$ROBOT" != "arm" && "$ROBOT" != "hexapod" ]]; then
  usage >&2
  exit 2
fi

python3 - "$ROOT_DIR" "$ROBOT" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "src"))
from acamp_robots.config import RobotConfig, save_config

path = save_config(RobotConfig(robot=sys.argv[2]), root)
print(f"設定を書きました: {path}")
PY

python3 -m venv "$ROOT_DIR/.venv"
"$ROOT_DIR/.venv/bin/python" -m pip install -e "$ROOT_DIR"

if [[ "$ROBOT" == "arm" ]]; then
  echo "DOFBOT を選びました。README に従って hardware/Arm_Lib.py を配置してください。"
else
  echo "Freenove Hexapod を選びました。README に従って vendor server を配置してください。"
fi

