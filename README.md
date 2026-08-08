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

Setup always installs the offline test runner and creates the Git-ignored
`projects/` research workspace. To prepare a Raspberry Pi for AprilTag/ArUco
camera research, do this once before camp:

```bash
./scripts/setup.sh --robot hexapod --research-vision \
  --hexapod-server-dir "$HOME/Freenove_Hexapod/Code/Server"
```

`--research-vision` installs NumPy and an OpenCV build containing the `aruco`
module, then fails setup if marker detection is unavailable. Both supported
robots create their virtual environments with access to system packages used
by Raspberry Pi cameras and vendor images.

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
image_path = robot.camera_capture("view.jpg")
robot.led_color(20, 0, 20)
robot.rest()  # Disable servo torque.
```

`home` moves to `[90, 90, 90, 90, 90, 180]`, with the arm upright and the gripper closed.

DOFBOT supports joint-angle reads, bounded six-joint movement, buzzer control, forward-kinematics estimates through `tool_position`, the legacy color/garbage-sorting poses through `move_preset`, and parameterized Hexapod box-transfer poses through `hexapod_pose`. Every movement explicitly enables torque first, so a new CLI command works after a previous `rest` call. Joint 5 supports 0–270 degrees; the other joints support 0–180 degrees. Durations are restricted to 100–5000 ms.

Single-servo motion is disabled. A deployed DOFBOT routed the documented servo ID 6 command to an arm joint instead of the gripper, so `move_joint`, standalone `grip_object`, and `target_step` are unavailable. Reviewed sorting tasks change the gripper through the known-working six-servo array API while preserving the preceding values for joints 1–5.

The wrist camera moves with the arm. Two viewing poses are intentionally distinct:

- `camera_forward` (`[90, 60, 60, 60, 90, 180]`) uses the documented joint geometry for a centered, theoretically horizontal forward-camera pose with the gripper closed.
- `camera_work_area` (`[90, 120, 0, 0, 90, 30]`) looks down toward the board for color inspection and tracking.

Use `pose_info NAME` to inspect a pose's joints, purpose, and calculated tool position before moving. After changing the camera pose, capture a fresh image to verify the real view.

The arm instruction module includes every color-sorting and garbage-sorting coordinate from the 01 environment, including inspection, pickup, lift, and each destination pose. The standard tasks inspect a fresh camera image and use reviewed six-joint poses for the requested manipulation.

The instructions also state general embodied-planning invariants for smaller models: contact precedes grasp, grasp precedes lift, arrival precedes release, and release precedes withdrawal. Grasping and release change only joint 6 while joints 1–5 hold the contact pose; they are never merged with lifting or withdrawal.

Every arm movement waits for its complete servo duration plus the vendor-required 100 ms command interval before returning. Sequential CLI calls therefore cannot overlap an unfinished approach, gripper closure, and lift.

For the standard 3 cm camp boxes, `sort_color COLOR` and `sort_garbage CATEGORY` provide deterministic manipulation after visual classification. They enforce approach completion, joint-6-only grasp, lift, destination transfer, joint-6-only release, and return. A concurrent `stop` or `rest` creates a cross-process cancellation latch and disables torque before the next task movement.

After the gripper command has completed, sorting tasks add a separate 0.5-second beat before issuing the lift. The same beat separates release from withdrawal, making those physical states unambiguously sequential. Gripper steps use the six-servo array API with joints 1–5 unchanged; they never use the unreliable single-servo command.

In a session started by `scripts/start-agent.sh`, the staff safety check applies to the whole session. The agent executes bounded DOFBOT movements and complete requested sorting sequences without asking the member for repeated safety confirmations between movements.

Hexapod example:

```python
robot.call("stand")
robot.call("stop")
# Stop motion and switch servo power off.
robot.call("rest")
# Walk forward for one second. Named directions avoid vendor-coordinate mistakes.
robot.call("walk", "forward", 1.0)
# Turn clockwise for one second.
robot.call("turn", "clockwise", 1.0)
# Measure a relative 180-degree clockwise turn with the onboard gyroscope.
turn_result = robot.call("turn_by", "clockwise", 180)
# Use a named whole-body height.
robot.call("body_height", "high")
# Run a short, stoppable whole-body performance.
robot.call("perform", "rock_and_roll")
# Lift only human-numbered leg 1, then return it to its saved position.
robot.call("lift_leg", 1)
robot.call("lower_leg", 1)
# Capture a frame without initializing or enabling the servos.
image_path = robot.call("camera_capture", "view.jpg")
```

Use `forward`, `backward`, `left`, or `right` for participant-facing movement. The default step is 15; explicit steps from 1 through 30 are available for experiments. Requested walking and open-loop turning durations up to 30 seconds run as one smooth action; the server owns the final stop timer, so the client does not need to sleep and send a later stop. Use `turn_by DIRECTION DEGREES` for a gyro-measured relative rotation such as 180 or 360 degrees; it integrates MPU6050 Z-axis angular velocity, slows near the target, stays continuous through the requested turn, and uses an angle-scaled internal deadline of up to 30 seconds. It explicitly reports success or timeout and is not an absolute compass heading. Use `body_height` with `low`, `normal`, or `high` for named height changes. The lower-level `timed_move`, `position`, and `attitude` methods remain available for tested behaviors that need explicit coordinates; Freenove uses positive `y` for forward and positive `x` for right.

If motion becomes unexpected, run `scripts/hexapod-rpc.sh emergency-stop`. This asks the bridge to cancel activity and disable servo power, then independently asserts the Freenove servo-disable GPIO using `pinctrl` or `raspi-gpio`. The systemd-managed bridge also invokes that independent shutdown path whenever the bridge exits. The physical power switch remains the final stop when the Raspberry Pi itself is unavailable.

The bridge also exposes the complete capability surface from the previous `multimodal-hexapod-rpc.py` environment: both gait modes, bounded translation and rotation, speed, body position and attitude, IMU balance, camera-head control, buzzer and LED control, camera capture, ultrasonic distance, battery voltage, red-ball tracking, servo power, and per-leg position, servo-angle, and calibrated joint-angle control. Red-ball tracking processes fresh camera frames in memory and retains the former HSV threshold, contour-centroid calculation, and PID steering and distance controller. It smooths center and radius measurements, tolerates three consecutively dropped detections, and uses center and distance deadbands to avoid stop-start motion while still backing away when the ball is too close. Tracking telemetry is included in `status` for physical tuning.

Short expressive performances are available through `perform`: `nod`, `sway`, `bounce`, `curious`, `happy`, `thinking`, and `rock_and_roll`. They use bounded posture and head movements, finish in neutral posture, and can be interrupted by `stop`. Query `capabilities` for the authoritative method list:

Individual legs use human-facing numbers 1–6. `lift_leg LEG [LIFT]` raises only that leg by a bounded relative amount (default 30, range 5–40) and saves its previous position. `lower_leg LEG` restores it, while `lower_all_legs` restores every leg raised through this semantic API. Whole-body posture commands supersede those saved positions.

Research observation primitives include `imu_read [SAMPLES]` for acceleration,
angular velocity, and IMU temperature; `tilt_read [SAMPLES]` for gravity-derived
roll and pitch; `sonic` for one low-latency forward ultrasonic reading;
`distance_read [SAMPLES] [INTERVAL]` for a median, range, and the valid source
readings in centimeters; `power` for named supply measurements, where
`servo_voltage_v` is the first vendor ADC channel and `raspberry_pi_voltage_v`
is the second; `leg_positions` for all six current leg coordinates;
and `camera_capture` for a fresh image. `head_pose` provides named center, left,
right, up, and down camera-head positions. MPU6050 has no magnetometer, so no
API claims to provide an absolute yaw or compass direction.

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

## USB research sensors

Both robot controllers expose two local Raspberry Pi sensor primitives. They do
not move the robot and the Hexapod versions do not require its motion RPC bridge.
Driver registration, device diagnostics, power-test steps, and the checklist for
adding another sensor are in [`docs/usb-sensors.md`](docs/usb-sensors.md).

```bash
# Omron 2JCIE-BU01(F1): one CRC-checked structured environmental reading
.venv/bin/acamp-robot call environment_read

# CGS-M3C: analyze 1 second of audio in memory and return levels only
.venv/bin/acamp-robot call microphone_level 1.0
```

`environment_read` returns temperature, relative humidity, ambient light,
barometric pressure, sound noise, eTVOC, eCO2, discomfort index, heat-stroke
index, and vibration measures. It follows Omron's USB serial sample protocol at
115200 bps and auto-detects USB ID `0590:00d4`. On systems where the device does
not bind automatically, follow the documented `ftdi_sio` registration before
the participant session. An explicit serial path such as `/dev/ttyUSB0` may be
passed as the first argument.

`microphone_level` accepts 0.1–5.0 seconds and returns RMS and peak dBFS. It uses
ALSA `arecord`, selects the first USB Audio card when possible, keeps PCM only in
memory, and writes no recording or voice data to disk. An explicit ALSA device
such as `plughw:2,0` may be passed as the second argument.

Test these first on an externally powered DOFBOT Raspberry Pi. Before moving the
sensors to a battery-powered Hexapod, stop both robots, have staff move the USB
devices, and check that the Hexapod remains stable while reading each sensor for
only one short trial. A USB disconnect, undervoltage warning, reset, or unstable
reading ends the test; do not retry until staff inspect power and connections.

## Robot skills

Reusable participant-created behaviors belong in [`skills/`](skills/), with one directory per behavior. These robot skills should use the public `acamp_robots` API and include an offline test where practical. They are separate from Codex skills and must not be installed into `~/.codex/skills`.

## Local research projects

Member experiments should begin in the Git-ignored `projects/` workspace. This
keeps local code, observations, and captures out of the public repository and
prevents a routine `git pull` from colliding with active research work.

Create a project with a lowercase descriptive name:

```bash
.venv/bin/python scripts/new-project.py turn-around
cd projects/turn-around
../../.venv/bin/pytest -q test_behavior.py
```

The generated project contains a no-motion test double, a `behavior.py`
starting point, a bounded Hexapod sequence example, an optional marker-vision
example, and an anonymous JSON Lines experiment log. `ExperimentLog` records a question, hypothesis, parameters,
observation, result, and relative artifact paths without requiring participant
identity.

`run_hexapod_sequence` accepts semantic posture, head, named walking/turning,
numbered-leg, performance, light, and buzzer calls. It rejects raw `move` and
raw servo methods, limits pauses and estimated total duration, and calls
`stop` after completion, interruption, or failure. Members can therefore make
new bounded expressions such as a Noh-inspired movement without changing or
pulling a new bridge version.

The marker helper deliberately provides observations rather than a finished
navigation algorithm:

```python
from acamp_robots.vision import detect_markers, horizontal_error

markers = detect_markers("view.jpg")
error_px = horizontal_error(markers[0], image_width=400)
```

It uses OpenCV's `DICT_APRILTAG_36h11` dictionary by default. A member can use
the detected marker ID, corners, center, and pixel error to investigate a
closed-loop `turn_by` behavior without changing the robot bridge.

Check preparation before camp or before assigning a vision project:

```bash
.venv/bin/acamp-doctor --root .
.venv/bin/acamp-doctor --root . --strict-vision
```

The first command checks the configuration, virtual environment, projects
workspace, and reports optional vision support. The strict form fails if
NumPy, OpenCV, or the AprilTag-capable marker backend is missing.

## Development and testing

No physical robot is required:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

The tests replace the external `Arm_Lib.py` and Unix-socket RPC endpoint with test doubles, allowing control logic to be checked before using real hardware.

Setup creates the virtual environment with access to Raspberry Pi system packages because vendor camera and OpenCV components are installed separately on the robot images. It also installs pytest for participant test-driven work. Existing Raspberry Pis configured before the research workspace was introduced should rerun `setup.sh` once; normal later code updates need only `git pull` and `start-agent.sh`.

## Safety

- Keep faces, fingers, and cables outside the arm and leg movement areas.
- Begin with slow, small movements.
- Test with the robot's power switch within immediate reach.
- `scripts/stop-camera-containers.sh` stops every running Docker container. Use it only on a dedicated robot Raspberry Pi.
