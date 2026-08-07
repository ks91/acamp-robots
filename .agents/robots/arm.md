# Yahboom DOFBOT Instructions

## Runtime and preparation

- This module applies only when `.acamp-robot.json` selects `arm`.
- Load the separately installed vendor library from the configured `arm_lib`, defaulting to `hardware/Arm_Lib.py`. Never copy or commit `Arm_Lib.py`.
- Before the first session after boot, `scripts/start-agent.sh` runs `scripts/stop-camera-containers.sh` to release the camera. That script stops all Docker containers and is appropriate only on a dedicated robot Raspberry Pi.
- Use `.venv/bin/acamp-robot call ...`; do not import `Arm_Lib.py` directly.
- When `ACAMP_PHYSICAL_ROBOT_READY=1`, staff have completed the session-level movement-area check. Execute supported bounded arm requests directly without asking the member to confirm safety, readiness, clearance, or access to the power switch.
- This no-confirmation rule includes home, camera poses, joint movements within limits, creative gestures, target centering, gripping a stated object width, and the documented color- and garbage-sorting sequences. Do not insert a new confirmation between stages of one requested sequence.
- Stop without questioning the member only when an actual hazard is reported or observed, the session is not prepared, hardware control fails, or the requested movement cannot stay within enforced limits. State the concrete problem and involve nearby staff; do not turn ordinary operation into a safety quiz.

## Body and public API

- Joints 1–6 are base rotation, lower link, middle link, upper link, wrist rotation, and gripper.
- Joints 1–4 and 6 accept 0–180 degrees. Joint 5 accepts 0–270 degrees. Never guess or bypass these enforced ranges.
- Public calls include `home`, `move_joint`, `read_joint`, `move_joints`, `stop`, `rest`, `camera_capture`, `led_color`, `buzzer_on`, `buzzer_off`, `grip_object`, `tool_position`, `move_preset`, `pose_info`, `target_step`, and `hexapod_pose`.
- Map `まっすぐ立って`, `ホームポジション`, and "go home" to `.venv/bin/acamp-robot call home`.
- Home is `[90, 90, 90, 90, 90, 180]`: upright with the gripper closed. Do not substitute the open angle 30 used by viewing and pickup poses.
- Map `休め`, `休んで`, `おやすみ`, `寝て`, `力を抜いて`, emergency stop, and explicit torque-off requests to `.venv/bin/acamp-robot call rest`. Both `stop` and `rest` disable servo torque. Use `home` for a stable upright pose.
- For an object with a stated width from 0 through 6.4 cm, call `grip_object WIDTH_CM`. Never guess a tight gripper angle when width is unknown; incorrect tight angles can stall and damage the servo.
- A movement call explicitly enables torque first, including after a previous CLI process handled `rest`; members should not have to know or repair that process boundary.

## Embodied planning

- Before manipulating an object, silently plan the physical states in order: observe, approach with the gripper open, arrive at the object, close the gripper without moving the arm, lift, carry while maintaining grip, arrive at the destination, open the gripper without moving the arm, and withdraw. Execute promptly; do not recite the plan or ask the member to approve each state.
- Contact must happen before grasp, grasp before lift, arrival before release, and release before withdrawal. Never lift while first closing the gripper, and never withdraw while first opening it.
- Change only the joints required for the current physical action. `move_joint 6 ANGLE` and `grip_object WIDTH_CM` change only the gripper and preserve joints 1–5. Use one of them for grasping or releasing; do not send a six-joint lift or destination pose until that gripper-only command has completed.
- The controller waits for the full servo duration before returning. Issue approach, gripper-only closure, and lift as separate sequential CLI calls; never run them in parallel or in the background.
- A named pose is a body configuration, not proof that its physical purpose has happened. Reaching `color_grab` means the open gripper is at the box; it does not mean the box is held. Reaching a destination with a closed gripper does not mean the box has been released.
- Preserve state deliberately between commands. While carrying an object, retain the actual joint-6 gripping angle in the next six-joint pose. Do not reset unrelated joints merely because a preset contains convenient defaults.
- Use evidence rather than assuming physical success. Joint reads can confirm commanded angles and a fresh camera image can confirm visible position. Never claim that an object was grasped, carried, sorted, or released solely because a command returned successfully.

## Geometry and camera poses

- Joint 1 controls horizontal direction: 90 degrees is directly forward, smaller is right, and larger is left.
- Approximate end-effector elevation is `joint2 + joint3 + joint4 - 180` degrees. Near 0 is horizontal and forward.
- The wrist camera is between joints 4 and 5, about 50.3 mm from the arm axis and 3.7 mm behind the wrist reference. It rotates with the base and follows end-effector pitch.
- `camera_forward` is `[90, 60, 60, 60, 90, 180]`: the base is centered, joints 2–4 total 180 degrees for a theoretical horizontal camera direction, the wrist is neutral, and the otherwise-unused gripper is closed. Map `前を向いて` and `カメラを前に向けて` to `move_preset camera_forward`.
- `camera_work_area` is `[90, 120, 0, 0, 90, 30]`, aimed down toward the board for color inspection and red-ball tracking. Do not interchange it with `camera_forward`.
- Use `.venv/bin/acamp-robot call pose_info POSE_NAME` when pose meaning or geometry is needed. After repositioning, capture a fresh image before claiming what the camera sees.

## Expressive and collaborative motion

- Treat requests for dance, acting, gestures, or styles such as rock, Noh, curious, happy, surprised, or sleepy as creative programming requests, not unsupported fixed-command requests. Compose a short bounded sequence from `move_joints`, `move_joint`, `move_preset`, LEDs, and the buzzer, using the member's words as design direction.
- Keep each commanded transition within the public joint and duration limits, preserve the gripper state unless the member requests a grip action, and finish in `home` or another clearly stated stable pose. Do not refuse merely because there is no preset with the exact artistic name.
- During exploration, put reusable expressive behaviors and their offline tests under `skills/` as described by the common instructions.

## Legacy task poses

- The following 01 color-sorting coordinates are authoritative. They are named presets, but the member and agent may combine them creatively rather than treating sorting as a fixed task:
  - inspect the box: `color_view` = `[90, 120, 0, 0, 90, 30]`
  - approach with the gripper open: `color_grab` = `[90, 43, 36, 40, 90, 30]`
  - lift a held box: `color_lift` = `[90, 80, 35, 40, 90, 135]`
  - red destination: `color_red` = `[117, 19, 66, 56, 90, 135]`
  - blue destination: `color_blue` = `[44, 66, 20, 28, 90, 135]`
  - green destination: `color_green` = `[136, 66, 20, 29, 90, 135]`
  - yellow destination: `color_yellow` = `[65, 22, 64, 56, 90, 135]`
- For a 3 cm box, close the gripper to approximately 134–135 degrees after reaching `color_grab`; use 30 degrees to release it. For another measured width, use `grip_object WIDTH_CM` rather than guessing.
- The following 01 garbage-sorting coordinates are authoritative:
  - inspect the attached item: `garbage_view` = `[90, 90, 15, 20, 90, 30]`
  - approach with the gripper open: `garbage_grab` = `[90, 40, 30, 67, 265, 30]`
  - lift a held box: `garbage_lift` = `[90, 80, 50, 50, 265, 135]`
  - hazardous/red destination: `garbage_hazardous` = `[45, 80, 35, 40, 265, 135]`
  - recyclable/blue destination: `garbage_recyclable` = `[27, 110, 0, 40, 265, 135]`
  - kitchen/green destination: `garbage_kitchen` = `[152, 110, 0, 40, 265, 135]`
  - other/gray destination: `garbage_other` = `[137, 80, 35, 40, 265, 135]`
- To classify either kind of box, move to its inspection pose, capture a fresh image, inspect the actual image, and decide from visible evidence. Then compose the pickup, grip, lift, destination, release, and return movements from the coordinates above. Do not claim a color, item, or garbage category from status or a stale image.
- For both layouts, separate pickup into three commands: move to the open-gripper grab pose; close only joint 6; then move to the lift pose. Separate placement into three commands: arrive while maintaining grip; open only joint 6; then withdraw. Never merge adjacent commands in either three-command sequence.
- For a known 3 cm color box, the concrete order is `move_preset color_grab`, then `move_joint 6 135`, then `move_preset color_lift`. Garbage sorting uses `move_preset garbage_grab`, then `move_joint 6 135`, then `move_preset garbage_lift`. At a destination, call `move_joint 6 30` before `home` or any withdrawal movement.
- Move through `home` before switching between separated inspection, pickup, and destination areas when the direct path could collide with a box, board, another robot, or the table. Preserve the held gripper angle until the box reaches its destination.
- For collaboration with a Hexapod carrying a box, use `hexapod_pose look|grab|drop BASE_ANGLE`. The base angle is deliberately supplied at runtime because the Hexapod may approach from different directions. Use camera observations and bounded `target_step` corrections instead of guessing that angle.

## Target tracking

- Capture and inspect a fresh image, divide it into 11 vertical sections, and call `target_step SECTION` with the target center's section. Section 6 is centered; use `not_present` if absent.
- Recheck after every five-degree step, stop after at most 10 steps, and honor any participant stop request immediately.
