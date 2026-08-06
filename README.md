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

The selection is stored in `.acamp-robot.json` using a robot name and a generic `settings` object. This device-specific file is not tracked by Git. Run setup again to change the robot. Existing flat configuration files from earlier versions are migrated when read.

Robot-specific settings can be supplied without adding setup-script flags:

```bash
./scripts/setup.sh --robot hexapod \
  --set hexapod_server_dir="$HOME/Freenove_Hexapod/Code/Server"
```

## Modular agent instructions

[`AGENTS.md`](AGENTS.md) is an instruction router. At session start, an agent reads:

1. [`CAMP.md`](CAMP.md) for the current program;
2. [`.agents/common.md`](.agents/common.md) for shared operation, safety, development, and safeguarding rules;
3. exactly one robot module selected from `.acamp-robot.json` through [`robots.json`](robots.json).

DOFBOT instructions live in [`.agents/robots/arm.md`](.agents/robots/arm.md), while Hexapod instructions live in [`.agents/robots/hexapod.md`](.agents/robots/hexapod.md). An unconfigured development checkout loads no robot module and must not infer hardware from files.

Use `CAMP.md` only for details that change between Academy Camp programs, such as:

- camp title, dates, and theme;
- the robot's role and interaction style;
- participant-facing language;
- permitted autonomous reactions;
- program-specific safety, safeguarding, and operating notes.

Update and commit `CAMP.md` before deploying each camp. Do not put robot-specific body knowledge back into root `AGENTS.md` or the common module.

## Robot plugin architecture

[`robots.json`](robots.json) is the single registry for supported robot types. Each entry owns:

- its controller factory import path;
- robot-specific instruction module;
- idempotent session-preparation command;
- virtual-environment system-package policy;
- default device settings and setup message.

`RobotConfig` stores arbitrary device settings, `create_controller` loads the registered factory, and both setup and session preparation consume the same registry. They do not contain `if arm` / `if hexapod` branches.

Adding another robot requires one registry entry, a controller factory, a preparation command, one instruction module, offline tests, and a documented physical acceptance test. The complete checklist is in [`.agents/README.md`](.agents/README.md). A robot is not supported merely because its name was added to the registry.

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
robot.home()
robot.move_joint(1, 100, duration_ms=500)
image_path = robot.camera_capture("view.jpg")
robot.led_color(20, 0, 20)
robot.grip_object(3.0)
robot.rest()  # Disable servo torque.
```

`home` moves to `[90, 90, 90, 90, 90, 180]`, with the arm upright and the gripper closed.

DOFBOT also supports joint-angle reads, bounded six-joint movement, buzzer control, measured object-width-to-gripper-angle conversion, forward-kinematics estimates through `tool_position`, the legacy color/garbage-sorting poses through `move_preset`, and five-degree visual-centering corrections through `target_step`. Joint 5 supports 0–270 degrees; the other joints support 0–180 degrees. Durations are restricted to 100–5000 ms.

The wrist camera moves with the arm. Two viewing poses are intentionally distinct:

- `camera_forward` (`[90, 60, 60, 60, 90, 120]`) faces ahead with horizontal end-effector elevation.
- `camera_work_area` (`[90, 120, 0, 0, 90, 30]`) looks down toward the board for color inspection and tracking.

Use `pose_info NAME` to inspect a pose's joints, purpose, and calculated tool position before moving. After changing the camera pose, capture a fresh image to verify the real view.

Hexapod example:

```python
robot.call("stand")
robot.call("stop")
# Stop motion and switch servo power off.
robot.call("rest")
# Walk forward for one second. Named directions avoid vendor-coordinate mistakes.
robot.call("walk", "forward", 1.0)
# Capture a frame without initializing or enabling the servos.
image_path = robot.call("camera_capture", "view.jpg")
```

Use `forward`, `backward`, `left`, or `right` for participant-facing movement. The bridge translates these names to Freenove's coordinate system and guarantees a server-side stop after at most five seconds. The lower-level `timed_move` method remains available for tested behaviors that need explicit coordinates; Freenove uses positive `y` for forward and positive `x` for right.

The bridge also exposes the capabilities from the previous `multimodal-hexapod-rpc.py` environment: buzzer and LED control, camera capture, ultrasonic distance, battery voltage, red-ball tracking, posture and head control, and per-leg position, servo-angle, and joint-angle control. Query `capabilities` for the authoritative method list:

```bash
.venv/bin/acamp-robot call capabilities
```

When a participant asks what the robot can see, the agent should call `camera_capture`, inspect the returned image file, and answer from the image. A status response contains no visual information. Camera capture deliberately works before servo initialization.

On the Hexapod, `stop` stops walking while retaining servo power and the current posture. `rest` stops motion and disables servo power. On DOFBOT, `stop` and `rest` disable servo torque. Participant expressions such as `休め`, `休んで`, and `おやすみ` map to `rest`.

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

DOFBOT setup creates the virtual environment with access to Raspberry Pi system packages because the vendor library and OpenCV are installed separately on the robot image. If an existing arm `.venv` was created without system packages, remove only that environment and rerun `./scripts/setup.sh --robot arm`.

## Safety

- Keep faces, fingers, and cables outside the arm and leg movement areas.
- Begin with slow, small movements.
- Test with the robot's power switch within immediate reach.
- `scripts/stop-camera-containers.sh` stops every running Docker container. Use it only on a dedicated robot Raspberry Pi.
