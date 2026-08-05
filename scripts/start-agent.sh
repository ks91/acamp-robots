#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT_DIR/scripts/prepare-session.sh"
cd "$ROOT_DIR"

if [[ -n "${LOGLM_BIN:-}" ]]; then
  exec "$LOGLM_BIN" -X "$@"
elif command -v loglm >/dev/null 2>&1; then
  exec loglm -X "$@"
elif [[ -x "$ROOT_DIR/../loglm/loglm" ]]; then
  exec "$ROOT_DIR/../loglm/loglm" -X "$@"
else
  echo "loglm was not found. Set LOGLM_BIN to its executable path." >&2
  exit 127
fi
