#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-start}"
SOCKET="${HEXAPOD_RPC_SOCKET:-/tmp/acamp-hexapod.sock}"
PID_FILE="${HEXAPOD_RPC_PID_FILE:-/tmp/acamp-hexapod-rpc.pid}"
LOG_FILE="${HEXAPOD_RPC_LOG:-/tmp/acamp-hexapod-rpc.log}"
BRIDGE="$ROOT_DIR/scripts/vendor_hexapod_bridge.py"
BRIDGE_PROTOCOL_VERSION=6
SYSTEMD_UNIT="acamp-hexapod-rpc"

if [[ -n "${HEXAPOD_SERVER_DIR:-}" ]]; then
  SERVER_DIR="$HEXAPOD_SERVER_DIR"
else
  SERVER_DIR="$(python3 - "$ROOT_DIR/.acamp-robot.json" <<'PY'
import json
import sys

try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("hexapod_server_dir", "hardware/freenove/Code/Server"))
except (FileNotFoundError, ValueError):
    print("hardware/freenove/Code/Server")
PY
)"
  [[ "$SERVER_DIR" = /* ]] || SERVER_DIR="$ROOT_DIR/$SERVER_DIR"
fi

read_pid() { [[ -f "$PID_FILE" ]] && tr -d '\n' < "$PID_FILE"; }

owned_process_alive() {
  local pid command
  pid="$(read_pid || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command" == *"vendor_hexapod_bridge.py"* && "$command" == *"$SOCKET"* ]]
}

user_systemd_available() {
  command -v systemctl >/dev/null 2>&1 &&
    command -v systemd-run >/dev/null 2>&1 &&
    systemctl --user show-environment >/dev/null 2>&1
}

managed_process_alive() {
  if user_systemd_available; then
    systemctl --user is-active --quiet "$SYSTEMD_UNIT.service"
  else
    owned_process_alive
  fi
}

rpc_ready() {
  [[ -S "$SOCKET" ]] || return 1
  python3 - "$SOCKET" "$BRIDGE_PROTOCOL_VERSION" <<'PY'
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
result = response.get("result", {})
ready = (
    response.get("ok")
    and result.get("pong")
    and result.get("protocol_version") == int(sys.argv[2])
)
raise SystemExit(0 if ready else 1)
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
    if user_systemd_available; then
      systemctl --user stop "$SYSTEMD_UNIT.service" >/dev/null 2>&1 || true
      systemctl --user reset-failed "$SYSTEMD_UNIT.service" >/dev/null 2>&1 || true
    fi
    if owned_process_alive; then
      kill "$(read_pid)" 2>/dev/null || true
    fi
    cleanup_stale_files
    printf '\n=== RPC start %s ===\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" >>"$LOG_FILE"
    if user_systemd_available; then
      systemd-run --user --quiet --collect \
        --unit="$SYSTEMD_UNIT" \
        --service-type=exec \
        --property=Restart=on-failure \
        --property=RestartSec=1 \
        --property="StandardOutput=append:$LOG_FILE" \
        --property="StandardError=append:$LOG_FILE" \
        --working-directory="$SERVER_DIR" \
        python3 "$BRIDGE" --socket "$SOCKET" --server-dir "$SERVER_DIR"
      systemctl --user show --property=MainPID --value "$SYSTEMD_UNIT.service" >"$PID_FILE"
    else
      nohup python3 "$BRIDGE" --socket "$SOCKET" --server-dir "$SERVER_DIR" >>"$LOG_FILE" 2>&1 &
      echo $! > "$PID_FILE"
    fi
    for _ in {1..40}; do
      if rpc_ready; then
        echo "The hexapod RPC bridge has started."
        exit 0
      fi
      managed_process_alive || break
      sleep 0.25
    done
    cleanup_stale_files
    echo "The RPC bridge failed to start. See: $LOG_FILE" >&2; exit 1
    ;;
  status) rpc_ready && echo "The hexapod RPC bridge is running." || { echo "The bridge is stopped."; exit 1; } ;;
  stop)
    rpc_shutdown >/dev/null 2>&1 || true
    for _ in {1..20}; do
      managed_process_alive || break
      sleep 0.1
    done
    if user_systemd_available; then
      systemctl --user stop "$SYSTEMD_UNIT.service" >/dev/null 2>&1 || true
    elif owned_process_alive; then
      kill "$(read_pid)"
    fi
    cleanup_stale_files
    ;;
  *) echo "Usage: $0 start|status|stop" >&2; exit 2 ;;
esac
