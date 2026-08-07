# Freenove Big Hexapod Instructions

## Runtime and preparation

- This module applies only when `.acamp-robot.json` selects `hexapod`.
- Control the robot through the local Unix-socket RPC bridge. Its hardware libraries belong to system Python and must not be imported into the project virtual environment.
- Vendor Server files default to `hardware/freenove/Code/Server` and may be overridden by `hexapod_server_dir` or `HEXAPOD_SERVER_DIR`. Never commit vendor files.
- `scripts/start-agent.sh` runs `scripts/hexapod-rpc.sh start`. On Raspberry Pi, the bridge uses a transient user systemd service and survives agent shell commands.
- After bridge changes, run `scripts/hexapod-rpc.sh start`; protocol mismatch replaces an incompatible old process.

## Initialization and posture

- `bridge_ready: true` with `hardware_initialized: false` is the normal state before servo activation. It does not mean vendor files or the robot are missing.
- In a prepared session, map a stand request directly to `.venv/bin/acamp-robot call stand`. `stand` performs first hardware initialization, enables servo power, and requests neutral posture.
- Do not inspect vendor source or refuse merely because hardware is uninitialized when a prepared-session participant requests `stand` or servo power.
- Map `止まれ` or "stop" to `stop`; it stops walking and retains servo power to hold posture.
- Map `休め`, `休んで`, `おやすみ`, `寝て`, `力を抜いて`, and servo-off requests to `.venv/bin/acamp-robot call rest`; it stops motion and disables servo power.

## Direction and bounded motion

- Use `.venv/bin/acamp-robot call walk DIRECTION DURATION` for forward, backward, left, and right. Valid names are `forward`, `backward`, `left`, and `right`; routine walks last at most five seconds. The default step is 15, not the ineffective five-unit step. An explicitly requested step may be 1–30.
- Never infer vendor coordinates from language. Freenove uses positive `y` for forward and positive `x` for right, but that mapping belongs inside `walk`.
- Use `.venv/bin/acamp-robot call turn DIRECTION DURATION` for named rotation. Map `時計回り`, `右回り`, and clockwise rotation to direction `clockwise`; map `反時計回り`, `左回り`, and counterclockwise rotation to `counterclockwise`. The default angle is 10 and the accepted range is 1–20. Do not emulate turning with left or right translation.
- Use `.venv/bin/acamp-robot call turn_by DIRECTION DEGREES` when a member requests a relative angle, such as `180度時計回りに回転して` or `真後ろを向いて`. `turn_by clockwise 180` integrates the MPU6050 Z-axis gyro, slows near the target, stops on success or after at most five seconds, and reports the measured relative angle and whether it reached the target. Do not translate 180 degrees into the low-level gait-angle parameter.
- `turn_by` measures a relative angle, not an absolute room direction. Requests above 180 degrees are automatically split into independently stopped, gyro-measured segments. MPU6050 has no magnetometer and does not provide an absolute compass heading. For repeatable room-relative directions, build a research behavior using camera markers or another external reference and use `turn_by` only for bounded corrections.
- Use `timed_move` only for tested behaviors requiring explicit coordinates. Never implement short movement as separate `move`, sleep, and `stop` agent commands.
- If motion is unexpected, run `scripts/hexapod-rpc.sh emergency-stop`. It first requests an RPC stop and then independently drives Freenove's active-high GPIO 4 servo-disable line, so it does not depend on a healthy bridge. If that command fails or the Pi is unreachable, use the physical power switch immediately and call staff. Never retry the movement first.

## Body, head, and expressive posture

- Map requests to become lower, normal height, or higher to `.venv/bin/acamp-robot call body_height LEVEL`, where LEVEL supports `low`, `normal`, and `high`. In Japanese, `低くして` maps to `low`, `普通の高さ` to `normal`, and `高くして` to `high`.
- `position X Y Z` translates the body and `attitude ROLL PITCH YAW` tilts it. Use these bounded vendor posture controls for explicit research behaviors; return to `position 0 0 0` and `attitude 0 0 0` for neutral posture.
- `head_horizontal ANGLE` turns the camera head: 90 is center, smaller angles look right, and larger angles look left. `head_vertical ANGLE` tilts it vertically: 90 is straight ahead, with a supported range of 60–180.
- Use `head_pose center|left|right|up|down` for ordinary named camera-head requests. Use explicit head angles when the angle itself is the experiment variable.
- `balance true` enables IMU balance and `balance false` disables it. Do not leave balance mode running when the participant asks to stop or rest.
- Do not refuse an imaginative request merely because it is imaginative. Small, bounded, stoppable posture choreography is routine supported motion in a prepared session.
- Map requests for a rock-and-roll movement, including `ロックンロールな動き`, to `.venv/bin/acamp-robot call perform rock_and_roll`. Other built-in short performances are `nod`, `sway`, `bounce`, `curious`, `happy`, and `thinking`; query `capabilities` and use `perform STYLE` rather than improvising unbounded shell-side sleeps.
- For a new creative movement, help the member make a tested behavior under `skills/` from bounded `position`, `attitude`, head, `walk`, and `turn` calls. Decline only the unsafe part of a request, not creativity itself.

## Individual legs

- Human-facing leg numbers are 1 through 6 and map directly to Freenove leg indices 0 through 5. Never pass a participant's 1-based number directly to a zero-based low-level leg method.
- Map requests such as `1番の脚だけ上げて` or “lift leg 1” to `.venv/bin/acamp-robot call lift_leg LEG_NUMBER`. The default lift is 30; an explicitly requested lift may be 5–40. This semantic call stops walking or tracking first, changes only that leg, and remembers its prior position.
- Map `1番の脚を下ろして` to `.venv/bin/acamp-robot call lower_leg LEG_NUMBER`. Map requests to lower every raised leg to `lower_all_legs`. These restore the positions saved by `lift_leg`.
- Whole-body `position`, `attitude`, `stand`, or performance changes supersede saved individual-leg positions. After one of those actions, make a fresh `lift_leg` request rather than trying to restore stale coordinates.

## Camera and peripherals

- Camera capture is available while `hardware_initialized` is false and must not initialize or enable servos. Do not move the robot merely to answer a visual question unless asked for a different view.
- Map a request to follow or chase the red ball to `ball_start`; it centers the head and continuously steers and moves both forward and backward to maintain its target distance. Its color threshold, contour centroid, and PID gains deliberately match the proven 01 implementation. Map requests to stop following to `ball_stop`, and use `ball_state` to inspect the tracker. Do not replace these with repeated camera captures or agent-generated movement commands.
- The RPC surface also provides a single ultrasonic distance (`sonic`), a robust multi-sample distance summary (`distance_read`), battery voltage (`power`), static RGB color (`led_color`), LED effects (`led_mode`), buzzer control, camera capture, red-ball tracking, head and whole-body posture control, balance, and per-leg position and angle control. Prefer `distance_read` for measured experiments and `sonic` when latency matters. Query `capabilities` rather than guessing method names.
- `.venv/bin/acamp-robot call imu_read` returns acceleration in m/s², angular velocity in degrees/second, temperature, and sample count. Use `.venv/bin/acamp-robot call tilt_read` for accelerometer-derived roll and pitch. `tilt_read` deliberately reports that yaw is unavailable rather than inventing a compass heading.
- `leg_positions` returns copies of the six current vendor-frame leg coordinates for observation and reproducible experiments; it does not move a leg.
- `lift_leg`, `lower_leg`, and `lower_all_legs` are routine semantic controls. Other manual per-leg calls are for deliberately programmed, reviewed behaviors only. Stop walking and ball tracking before using them; do not use raw servo angles for ordinary participant language.
