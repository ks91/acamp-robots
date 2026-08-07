# Yahboom DOFBOT Instructions

## Runtime and preparation

- This module applies only when `.acamp-robot.json` selects `arm`.
- Load the separately installed vendor library from the configured `arm_lib`, defaulting to `hardware/Arm_Lib.py`. Never copy or commit `Arm_Lib.py`.
- Before the first session after boot, `scripts/start-agent.sh` runs `scripts/stop-camera-containers.sh` to release the camera. That script stops all Docker containers and is appropriate only on a dedicated robot Raspberry Pi.
- Use `.venv/bin/acamp-robot call ...`; do not import `Arm_Lib.py` directly.

## Body and public API

- Joints 1–6 are base rotation, lower link, middle link, upper link, wrist rotation, and gripper.
- Joints 1–4 and 6 accept 0–180 degrees. Joint 5 accepts 0–270 degrees. Never guess or bypass these enforced ranges.
- Public calls include `home`, `move_joint`, `read_joint`, `move_joints`, `stop`, `rest`, `camera_capture`, `led_color`, `buzzer_on`, `buzzer_off`, `grip_object`, `tool_position`, `move_preset`, `pose_info`, `target_step`, and `hexapod_pose`.
- Map `まっすぐ立って`, `ホームポジション`, and "go home" to `.venv/bin/acamp-robot call home`.
- Home is `[90, 90, 90, 90, 90, 180]`: upright with the gripper closed. Do not substitute the open angle 30 used by viewing and pickup poses.
- Map `休め`, `休んで`, `おやすみ`, `寝て`, `力を抜いて`, emergency stop, and explicit torque-off requests to `.venv/bin/acamp-robot call rest`. Both `stop` and `rest` disable servo torque. Use `home` for a stable upright pose.
- For an object with a stated width from 0 through 6.4 cm, call `grip_object WIDTH_CM`. Never guess a tight gripper angle when width is unknown; incorrect tight angles can stall and damage the servo.
- A movement call explicitly enables torque first, including after a previous CLI process handled `rest`; members should not have to know or repair that process boundary.

## Geometry and camera poses

- Joint 1 controls horizontal direction: 90 degrees is directly forward, smaller is right, and larger is left.
- Approximate end-effector elevation is `joint2 + joint3 + joint4 - 180` degrees. Near 0 is horizontal and forward.
- The wrist camera is between joints 4 and 5, about 50.3 mm from the arm axis and 3.7 mm behind the wrist reference. It rotates with the base and follows end-effector pitch.
- `camera_forward` is the empirically adjusted pose `[90, 65, 115, 110, 90, 119]` from physical testing. Map `前を向いて` and `カメラを前に向けて` to `move_preset camera_forward`. Do not replace it with a pose derived only from idealized end-effector geometry; camera mounting and real servo geometry matter.
- `camera_work_area` is `[90, 120, 0, 0, 90, 30]`, aimed down toward the board for color inspection and red-ball tracking. Do not interchange it with `camera_forward`.
- Use `.venv/bin/acamp-robot call pose_info POSE_NAME` when pose meaning or geometry is needed. After repositioning, capture a fresh image before claiming what the camera sees.

## Expressive and collaborative motion

- Treat requests for dance, acting, gestures, or styles such as rock, Noh, curious, happy, surprised, or sleepy as creative programming requests, not unsupported fixed-command requests. Compose a short bounded sequence from `move_joints`, `move_joint`, `move_preset`, LEDs, and the buzzer, using the member's words as design direction.
- Keep each commanded transition within the public joint and duration limits, preserve the gripper state unless the member requests a grip action, and finish in `home` or another clearly stated stable pose. Do not refuse merely because there is no preset with the exact artistic name.
- During exploration, put reusable expressive behaviors and their offline tests under `skills/` as described by the common instructions.

## Legacy task poses

- Color and garbage sorting presets from the 01 environment remain available through `move_preset`; move through `home` between separated pickup and drop work areas when collision clearance is uncertain.
- For collaboration with a Hexapod carrying a box, use `hexapod_pose look|grab|drop BASE_ANGLE`. The base angle is deliberately supplied at runtime because the Hexapod may approach from different directions. Use camera observations and bounded `target_step` corrections instead of guessing that angle.

## Target tracking

- Capture and inspect a fresh image, divide it into 11 vertical sections, and call `target_step SECTION` with the target center's section. Section 6 is centered; use `not_present` if absent.
- Recheck after every five-degree step, stop after at most 10 steps, and honor any participant stop request immediately.
