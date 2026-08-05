#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker が見つかりません。カメラ用コンテナの停止をスキップします。"
  exit 0
fi

mapfile_compat="$(docker ps -q)"
if [[ -z "$mapfile_compat" ]]; then
  echo "停止する Docker コンテナはありません。"
  exit 0
fi

echo "カメラを解放するため、実行中の Docker コンテナを停止します。"
docker stop $mapfile_compat

