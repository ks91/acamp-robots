#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/.acamp-robot.json"

if [[ ! -f "$CONFIG" ]]; then
  echo "ロボットが未設定です。./scripts/setup.sh --robot arm|hexapod を実行してください。" >&2
  exit 2
fi

ROBOT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["robot"])' "$CONFIG")"

if [[ "$ROBOT" == "arm" ]]; then
  "$ROOT_DIR/scripts/stop-camera-containers.sh"
elif [[ "$ROBOT" == "hexapod" ]]; then
  "$ROOT_DIR/scripts/hexapod-rpc.sh" start
else
  echo "未対応のロボット設定: $ROBOT" >&2
  exit 2
fi

