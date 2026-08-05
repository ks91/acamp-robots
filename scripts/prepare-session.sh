#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/.acamp-robot.json"

if [[ ! -f "$CONFIG" ]]; then
  echo "No robot is configured. Run ./scripts/setup.sh --robot arm|hexapod first." >&2
  exit 2
fi

ROBOT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["robot"])' "$CONFIG")"

if [[ "$ROBOT" == "arm" ]]; then
  "$ROOT_DIR/scripts/stop-camera-containers.sh"
elif [[ "$ROBOT" == "hexapod" ]]; then
  "$ROOT_DIR/scripts/hexapod-rpc.sh" start
else
  echo "Unsupported robot configuration: $ROBOT" >&2
  exit 2
fi
