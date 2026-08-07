#!/usr/bin/env bash
set -euo pipefail

# Freenove's Control class uses BCM GPIO 4 as an active-high servo-power disable.
# This path deliberately does not depend on the Python RPC bridge.
if command -v pinctrl >/dev/null 2>&1; then
  exec pinctrl set 4 op dh
fi
if command -v raspi-gpio >/dev/null 2>&1; then
  exec raspi-gpio set 4 op dh
fi

echo "Cannot disable hexapod servo power: pinctrl/raspi-gpio is unavailable." >&2
exit 1
