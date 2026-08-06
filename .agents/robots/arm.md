# Yahboom DOFBOT Instructions

## Runtime and preparation

- This module applies only when `.acamp-robot.json` selects `arm`.
- Load the separately installed vendor library from the configured `arm_lib`, defaulting to `hardware/Arm_Lib.py`. Never copy or commit `Arm_Lib.py`.
- Before the first session after boot, `scripts/start-agent.sh` runs `scripts/stop-camera-containers.sh` to release the camera. That script stops all Docker containers and is appropriate only on a dedicated robot Raspberry Pi.
- Use `.venv/bin/acamp-robot call ...`; do not import `Arm_Lib.py` directly.

## Body and public API

- Joints 1–6 are base rotation, lower link, middle link, upper link, wrist rotation, and gripper.
- Joints 1–4 and 6 accept 0–180 degrees. Joint 5 accepts 0–270 degrees. Never guess or bypass these enforced ranges.
- Public calls include `home`, `move_joint`, `read_joint`, `move_joints`, `stop`, `rest`, `camera_capture`, `led_color`, `buzzer_on`, `buzzer_off`, `grip_object`, `tool_position`, `move_preset`, `pose_info`, and `target_step`.
- Map `まっすぐ立って`, `ホームポジション`, and "go home" to `.venv/bin/acamp-robot call home`.
- Home is `[90, 90, 90, 90, 90, 180]`: upright with the gripper closed. Do not substitute the open angle 30 used by viewing and pickup poses.
- Map `休め`, `休んで`, `おやすみ`, `寝て`, `力を抜いて`, emergency stop, and explicit torque-off requests to `.venv/bin/acamp-robot call rest`. Both `stop` and `rest` disable servo torque. Use `home` for a stable upright pose.
- For an object with a stated width, call `grip_object WIDTH_CM`. Never guess a tight gripper angle when width is unknown; incorrect tight angles can stall and damage the servo.

## Geometry and camera poses

- Joint 1 controls horizontal direction: 90 degrees is directly forward, smaller is right, and larger is left.
- Approximate end-effector elevation is `joint2 + joint3 + joint4 - 180` degrees. Near 0 is horizontal and forward.
- The wrist camera is between joints 4 and 5, about 50.3 mm from the arm axis and 3.7 mm behind the wrist reference. It rotates with the base and follows end-effector pitch.
- `camera_forward` is `[90, 60, 60, 60, 90, 120]`; joints 2–4 total 180 degrees for a horizontal forward-facing end effector. Map `前を向いて` and `カメラを前に向けて` to `move_preset camera_forward`.
- `camera_work_area` is `[90, 120, 0, 0, 90, 30]`, aimed down toward the board for color inspection and red-ball tracking. Do not interchange it with `camera_forward`.
- Use `.venv/bin/acamp-robot call pose_info POSE_NAME` when pose meaning or geometry is needed. After repositioning, capture a fresh image before claiming what the camera sees.

## Target tracking

- Capture and inspect a fresh image, divide it into 11 vertical sections, and call `target_step SECTION` with the target center's section. Section 6 is centered; use `not_present` if absent.
- Recheck after every five-degree step, stop after at most 10 steps, and honor any participant stop request immediately.
