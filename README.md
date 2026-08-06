# Academy Camp Robots

A small robot-control environment for using coding agents at the Academy Camp science camp. It intentionally does not depend on voice features, 01, or LiveKit.

Supported robots:

- Yahboom DOFBOT robot arm
- Freenove Big Hexapod Robot Kit

## Raspberry Pi setup

Clone this public repository onto the Raspberry Pi, then select the robot connected to that Pi:

```bash
git clone <repository-url> acamp-robots
cd acamp-robots
./scripts/setup.sh --robot arm       # DOFBOT
# or
./scripts/setup.sh --robot hexapod  # Freenove
```

If the Freenove Server is already installed elsewhere on the Raspberry Pi, save that absolute path in the device configuration:

```bash
./scripts/setup.sh --robot hexapod \
  --hexapod-server-dir "$HOME/Freenove_Hexapod/Code/Server"
```

The selection is stored in `.acamp-robot.json`. This is a device-specific file and is not tracked by Git. Run the setup command again to change the robot type.

## Camp-specific agent instructions

[`AGENTS.md`](AGENTS.md) requires coding agents to read [`CAMP.md`](CAMP.md) at the beginning of every session. Use `CAMP.md` for instructions that change between Academy Camp programs, such as:

- camp title, dates, and theme;
- the robot's role and interaction style;
- participant-facing language;
- permitted autonomous reactions;
- program-specific safety, safeguarding, and operating notes.

Update and commit `CAMP.md` before deploying the repository for each camp. Keep long-lived technical and safety rules in `AGENTS.md`.

## Vendor software locations

This repository does not redistribute vendor hardware-control software.

### DOFBOT

Place the `Arm_Lib.py` supplied with the DOFBOT at:

```text
hardware/Arm_Lib.py
```

The licensing terms for `Arm_Lib.py` do not appear to permit redistribution, so the file is excluded from this repository and listed in `.gitignore`. Copy it directly to each Raspberry Pi from the official DOFBOT image or another vendor-provided source.

### Freenove Hexapod

By default, place the complete Freenove Raspberry Pi Server directory at:

```text
hardware/freenove/Code/Server/main.py
hardware/freenove/Code/Server/control.py
...
```

Set `HEXAPOD_SERVER_DIR` to use another location. Review and follow the `LICENSE.txt` included with the Freenove distribution.

## Starting a session

Connect to the Raspberry Pi over SSH and run:

```bash
./scripts/start-agent.sh
```

The script prepares the selected robot and then starts `loglm -X`.

- DOFBOT: stops all running Docker containers to release the camera. The operation is idempotent and therefore reliably runs during the first session after every boot.
- Hexapod: starts the local Unix-socket RPC bridge if it is not already running.

`start-agent.sh` also exports `ACAMP_PHYSICAL_ROBOT_READY=1`. This represents a session-level safety handoff: staff clear and supervise the robot area before participants begin, and the coding agent executes routine bounded movement requests without repeatedly asking children to confirm safety. Calibration, disabled limits, unbounded walking, high-speed movement, and other out-of-policy operations remain unavailable rather than becoming confirmation prompts.

For development or diagnostic sessions that must not receive this standing authorization, use:

```bash
ACAMP_PHYSICAL_ROBOT_READY=0 ./scripts/start-agent.sh
```

Starting the Hexapod bridge does not initialize the vendor hardware or enable servo power. A status containing `bridge_ready: true` and `hardware_initialized: false` is therefore normal. In a prepared physical session, use `stand` to initialize the hardware, enable servo power, and request the neutral standing posture. Other movement commands are rejected until initialization succeeds.

On Raspberry Pi systems with an available user systemd manager, the bridge runs as a transient user service. This keeps it alive after an SSH or coding-agent shell command finishes. The script falls back to `nohup` on development systems without user systemd. After pulling bridge changes, run `./scripts/hexapod-rpc.sh start`; an incompatible older bridge is detected and replaced automatically.

The `-X` option suppresses individual execution-approval prompts. This prioritizes a smooth participant experience, but it also gives the coding agent broad authority. Do not store secrets or unnecessary credentials on the Raspberry Pi. Clear the area around the robot and ensure that an adult can cut its power immediately.

If `loglm` is not on `PATH`, specify its executable:

```bash
LOGLM_BIN=../loglm/loglm ./scripts/start-agent.sh
```

## Python API

```python
from pathlib import Path
from acamp_robots import create_controller, load_config

root = Path.cwd()
robot = create_controller(load_config(root), root)
```

DOFBOT example:

```python
robot.move_joints([90, 90, 90, 90, 90, 30], duration_ms=1000)
```

Hexapod example (`stand`, `move`, `timed_move`, `stop`, `speed`, `balance`, `position`, `attitude`, `head_vertical`, `head_horizontal`, and `servopower` are available over RPC):

```python
robot.call("stand")
robot.call("stop")
# Move for one second; the bridge guarantees the stop even if the client disconnects.
robot.call("timed_move", 1.0, 1, 5, 0, 0)
```

The command-line interface provides the same basic access:

```bash
.venv/bin/acamp-robot status
.venv/bin/acamp-robot call stop
```

## Robot skills

Reusable participant-created behaviors belong in [`skills/`](skills/), with one directory per behavior. These robot skills should use the public `acamp_robots` API and include an offline test where practical. They are separate from Codex skills and must not be installed into `~/.codex/skills`.

## Development and testing

No physical robot is required:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

The tests replace the external `Arm_Lib.py` and Unix-socket RPC endpoint with test doubles, allowing control logic to be checked before using real hardware.

## Safety

- Keep faces, fingers, and cables outside the arm and leg movement areas.
- Begin with slow, small movements.
- Test with the robot's power switch within immediate reach.
- `scripts/stop-camera-containers.sh` stops every running Docker container. Use it only on a dedicated robot Raspberry Pi.
