#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-start}"
SOCKET="${HEXAPOD_RPC_SOCKET:-/tmp/acamp-hexapod.sock}"
PID_FILE="${HEXAPOD_RPC_PID_FILE:-/tmp/acamp-hexapod-rpc.pid}"
LOG_FILE="${HEXAPOD_RPC_LOG:-/tmp/acamp-hexapod-rpc.log}"
SERVER_DIR="${HEXAPOD_SERVER_DIR:-$ROOT_DIR/hardware/freenove/Code/Server}"

alive() { [[ -f "$PID_FILE" ]] && kill -0 "$(tr -d '\n' < "$PID_FILE")" 2>/dev/null; }

case "$ACTION" in
  start)
    if alive; then echo "The hexapod RPC bridge is already running."; exit 0; fi
    if [[ ! -f "$SERVER_DIR/main.py" ]]; then
      echo "The Freenove server was not found: $SERVER_DIR" >&2
      exit 1
    fi
    rm -f "$SOCKET"
    nohup python3 "$ROOT_DIR/scripts/vendor_hexapod_bridge.py" --socket "$SOCKET" --server-dir "$SERVER_DIR" >>"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    for _ in {1..20}; do [[ -S "$SOCKET" ]] && { echo "The hexapod RPC bridge has started."; exit 0; }; sleep 0.25; done
    echo "The RPC bridge failed to start. See: $LOG_FILE" >&2; exit 1
    ;;
  status) alive && echo "The hexapod RPC bridge is running." || { echo "The bridge is stopped."; exit 1; } ;;
  stop) if alive; then kill "$(tr -d '\n' < "$PID_FILE")"; fi; rm -f "$PID_FILE" "$SOCKET" ;;
  *) echo "Usage: $0 start|status|stop" >&2; exit 2 ;;
esac
