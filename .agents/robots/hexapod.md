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
- Use `timed_move` only for tested behaviors requiring explicit coordinates. Never implement short movement as separate `move`, sleep, and `stop` agent commands.
- If the bridge disconnects during motion, use the physical power switch or `CAMP.md` emergency procedure rather than relying on another RPC request.

## Body, head, and expressive posture

- Map requests to become lower, normal height, or higher to `.venv/bin/acamp-robot call body_height LEVEL`, where LEVEL supports `low`, `normal`, and `high`. In Japanese, `低くして` maps to `low`, `普通の高さ` to `normal`, and `高くして` to `high`.
- `position X Y Z` translates the body and `attitude ROLL PITCH YAW` tilts it. Use these bounded vendor posture controls for explicit research behaviors; return to `position 0 0 0` and `attitude 0 0 0` for neutral posture.
- `head_horizontal ANGLE` turns the camera head: 90 is center, smaller angles look right, and larger angles look left. `head_vertical ANGLE` tilts it vertically: 90 is straight ahead, with a supported range of 60–180.
- `balance true` enables IMU balance and `balance false` disables it. Do not leave balance mode running when the participant asks to stop or rest.

## Camera and peripherals

- Camera capture is available while `hardware_initialized` is false and must not initialize or enable servos. Do not move the robot merely to answer a visual question unless asked for a different view.
- Map a request to follow or chase the red ball to `ball_start`; it centers the head and continuously steers and moves both forward and backward to maintain its target distance. Map requests to stop following to `ball_stop`, and use `ball_state` to inspect the tracker. Do not replace these with repeated camera captures or agent-generated movement commands.
- The RPC surface also provides ultrasonic distance (`sonic`), battery voltage (`power`), static RGB color (`led_color`), LED effects (`led_mode`), buzzer control, camera capture, red-ball tracking, head and whole-body posture control, balance, and per-leg position and angle control. Query `capabilities` rather than guessing method names.
- Manual per-leg calls are for deliberately programmed, reviewed behaviors only. Stop walking and ball tracking before using them; do not use raw servo angles for ordinary participant language.
