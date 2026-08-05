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
    if alive; then echo "ヘクサポッド RPC は起動済みです。"; exit 0; fi
    if [[ ! -f "$SERVER_DIR/main.py" ]]; then
      echo "Freenove server が見つかりません: $SERVER_DIR" >&2
      exit 1
    fi
    rm -f "$SOCKET"
    nohup python3 "$ROOT_DIR/scripts/vendor_hexapod_bridge.py" --socket "$SOCKET" --server-dir "$SERVER_DIR" >>"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    for _ in {1..20}; do [[ -S "$SOCKET" ]] && { echo "ヘクサポッド RPC を起動しました。"; exit 0; }; sleep 0.25; done
    echo "RPC の起動に失敗しました。ログ: $LOG_FILE" >&2; exit 1
    ;;
  status) alive && echo "ヘクサポッド RPC は起動中です。" || { echo "停止中です。"; exit 1; } ;;
  stop) if alive; then kill "$(tr -d '\n' < "$PID_FILE")"; fi; rm -f "$PID_FILE" "$SOCKET" ;;
  *) echo "使い方: $0 start|status|stop" >&2; exit 2 ;;
esac

