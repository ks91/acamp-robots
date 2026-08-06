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

- Use `.venv/bin/acamp-robot call walk DIRECTION DURATION` for forward, backward, left, and right. Valid names are `forward`, `backward`, `left`, and `right`; routine walks last at most five seconds.
- Never infer vendor coordinates from language. Freenove uses positive `y` for forward and positive `x` for right, but that mapping belongs inside `walk`.
- Use `timed_move` only for tested behaviors requiring explicit coordinates. Never implement short movement as separate `move`, sleep, and `stop` agent commands.
- If the bridge disconnects during motion, use the physical power switch or `CAMP.md` emergency procedure rather than relying on another RPC request.

## Camera and peripherals

- Camera capture is available while `hardware_initialized` is false and must not initialize or enable servos. Do not move the robot merely to answer a visual question unless asked for a different view.
- The RPC surface also provides ultrasonic distance, battery voltage, LED, buzzer, red-ball tracking, head/posture control, and per-leg position and angle control. Query `capabilities` rather than guessing method names.
