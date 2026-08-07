#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADMIN="$ROOT_DIR/scripts/robot-admin.py"
ROBOT=""
SETTINGS=()
RESEARCH_VISION=0

usage() {
  local robots
  robots="$(python3 "$ADMIN" list --separator '|')"
  echo "Usage: ./scripts/setup.sh --robot $robots [--set KEY=VALUE] [--research-vision]"
  echo "Compatibility option: --hexapod-server-dir PATH"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --robot) ROBOT="${2:-}"; shift 2 ;;
    --set) SETTINGS+=("${2:-}"); shift 2 ;;
    --hexapod-server-dir) SETTINGS+=("hexapod_server_dir=${2:-}"); shift 2 ;;
    --research-vision) RESEARCH_VISION=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$ROBOT" ]]; then
  usage >&2
  exit 2
fi

CONFIGURE=(python3 "$ADMIN" configure --robot "$ROBOT")
for setting in "${SETTINGS[@]}"; do
  CONFIGURE+=(--set "$setting")
done
"${CONFIGURE[@]}"

VENV_ARGS=()
if [[ "$(python3 "$ADMIN" field "$ROBOT" system_site_packages)" == "true" ]]; then
  VENV_ARGS+=(--system-site-packages)
fi
python3 -m venv "${VENV_ARGS[@]}" "$ROOT_DIR/.venv"
EXTRAS="dev"
if [[ "$RESEARCH_VISION" == "1" ]]; then
  EXTRAS="dev,vision"
fi
"$ROOT_DIR/.venv/bin/python" -m pip install -e "$ROOT_DIR[$EXTRAS]"
mkdir -p "$ROOT_DIR/projects"
python3 "$ADMIN" field "$ROBOT" setup_note
DOCTOR_ARGS=(--root "$ROOT_DIR")
if [[ "$RESEARCH_VISION" == "1" ]]; then
  DOCTOR_ARGS+=(--strict-vision)
fi
"$ROOT_DIR/.venv/bin/acamp-doctor" "${DOCTOR_ARGS[@]}"
