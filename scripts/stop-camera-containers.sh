#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker was not found; skipping camera-container shutdown."
  exit 0
fi

mapfile_compat="$(docker ps -q)"
if [[ -z "$mapfile_compat" ]]; then
  echo "No running Docker containers were found."
  exit 0
fi

echo "Stopping running Docker containers to release the camera."
docker stop $mapfile_compat
