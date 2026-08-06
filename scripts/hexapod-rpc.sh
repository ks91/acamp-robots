#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-start}"
SOCKET="${HEXAPOD_RPC_SOCKET:-/tmp/acamp-hexapod.sock}"
PID_FILE="${HEXAPOD_RPC_PID_FILE:-/tmp/acamp-hexapod-rpc.pid}"
LOG_FILE="${HEXAPOD_RPC_LOG:-/tmp/acamp-hexapod-rpc.log}"
SERVER_DIR="${HEXAPOD_SERVER_DIR:-$ROOT_DIR/hardware/freenove/Code/Server}"
BRIDGE="$ROOT_DIR/scripts/vendor_hexapod_bridge.py"

read_pid() { [[ -f "$PID_FILE" ]] && tr -d '\n' < "$PID_FILE"; }

owned_process_alive() {
  local pid command
  pid="$(read_pid || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command" == *"vendor_hexapod_bridge.py"* && "$command" == *"$SOCKET"* ]]
}

rpc_ready() {
  [[ -S "$SOCKET" ]] || return 1
  python3 - "$SOCKET" <<'PY'
import json
import socket
import sys

try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        client.connect(sys.argv[1])
        client.sendall(b'{"id":"health","method":"ping","args":[],"kwargs":{}}\n')
        response = json.loads(client.recv(4096).split(b"\n", 1)[0])
except (OSError, ValueError):
    raise SystemExit(1)
raise SystemExit(0 if response.get("ok") and response.get("result", {}).get("pong") else 1)
PY
}

rpc_shutdown() {
  [[ -S "$SOCKET" ]] || return 1
  python3 - "$SOCKET" <<'PY'
import json
import socket
import sys

try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(sys.argv[1])
        client.sendall(b'{"id":"stop","method":"shutdown","args":[],"kwargs":{}}\n')
        response = json.loads(client.recv(4096).split(b"\n", 1)[0])
except (OSError, ValueError):
    raise SystemExit(1)
raise SystemExit(0 if response.get("ok") else 1)
PY
}

cleanup_stale_files() {
  rm -f "$PID_FILE" "$SOCKET"
}

case "$ACTION" in
  start)
    if rpc_ready; then echo "The hexapod RPC bridge is already running."; exit 0; fi
    if [[ ! -f "$SERVER_DIR/main.py" ]]; then
      echo "The Freenove server was not found: $SERVER_DIR" >&2
      exit 1
    fi
    if owned_process_alive; then
      kill "$(read_pid)" 2>/dev/null || true
    fi
    cleanup_stale_files
    printf '\n=== RPC start %s ===\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" >>"$LOG_FILE"
    nohup python3 "$BRIDGE" --socket "$SOCKET" --server-dir "$SERVER_DIR" >>"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    for _ in {1..40}; do
      if rpc_ready; then
        echo "The hexapod RPC bridge has started."
        exit 0
      fi
      owned_process_alive || break
      sleep 0.25
    done
    cleanup_stale_files
    echo "The RPC bridge failed to start. See: $LOG_FILE" >&2; exit 1
    ;;
  status) rpc_ready && echo "The hexapod RPC bridge is running." || { echo "The bridge is stopped."; exit 1; } ;;
  stop)
    rpc_shutdown >/dev/null 2>&1 || true
    for _ in {1..20}; do
      owned_process_alive || break
      sleep 0.1
    done
    if owned_process_alive; then kill "$(read_pid)"; fi
    cleanup_stale_files
    ;;
  *) echo "Usage: $0 start|status|stop" >&2; exit 2 ;;
esac
