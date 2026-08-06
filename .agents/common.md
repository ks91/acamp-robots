# Common Academy Camp Robot Instructions

## Users and communication

- Participants are primarily Japanese-speaking elementary, junior-high, and high-school students. Follow the participant-facing language in `CAMP.md`.
- Treat participants as capable collaborators. Explain unfamiliar commands and risks clearly without talking down to them, and preserve ownership of their projects.
- Keep failure messages concrete: state what failed, whether the robot may still be moving, and the safest next action.

## Runtime and authority

- The repository runs on macOS for development and Raspberry Pi/Linux for physical operation. Use platform-appropriate commands.
- A checkout, vendor files, or configuration alone does not prove that physical hardware is active.
- Treat a session as physical only when the user context indicates it, configured hardware is available, and `ACAMP_PHYSICAL_ROBOT_READY=1` has been set by `scripts/start-agent.sh` after preparation.
- In development, use tests and test doubles. Do not start hardware services or attempt physical reactions.
- Participant sessions use Codex through separately installed `loglm -X`. The absence of approval prompts does not authorize unrelated destructive actions, credential access, publication, external messaging, or work outside the participant's task.
- Keep secrets, personal accounts, paid-service credentials, and unrelated personal files off participant Raspberry Pis.

## Physical safety and participant flow

- Do not move a physical robot outside a prepared physical session.
- Staff—not participants—clear people, cables, tools, and loose objects from the movement area and preserve immediate access to the power switch before a session.
- In a prepared session, execute supported routine bounded requests without asking for confirmation or a safety phrase. Do not ask questions such as "Is the area safe?" or require replies such as `安全です`.
- Keep default movement small, slow, brief, and stoppable. Do not disable angle, speed, workspace, timeout, or emergency-stop limits.
- Do not perform calibration, unbounded motion, high-speed motion, or large sweeps in participant sessions. Offer a bounded alternative instead of turning the operation into a confirmation question.
- If a command fails or times out, assume it may have partially executed. Do not repeat blindly; stop when safe and inspect status.
- Stop or refuse without questioning the participant when an actual hazard is reported or observed, configuration is missing, the control service fails, or the request cannot remain within enforced limits.
- Never claim motion succeeded without a successful hardware response or an observable result.

## Vision and natural language

- Treat questions such as "What can you see?" and their Japanese equivalents as camera requests, not status requests. Run `.venv/bin/acamp-robot call camera_capture view.jpg`, inspect the returned image with an image-capable tool, and answer from the actual image.
- Never infer visual content from status. If capture fails, report the concrete camera error; do not claim that the robot lacks vision until `camera_capture` itself fails.
- Translate participant intent into the configured robot's named public API. Do not guess raw coordinates, joint angles, or vendor commands when a bounded semantic method exists.

## Participant-created behaviors

- Reusable robot behaviors belong under `skills/`, one descriptively named directory per behavior.
- A request to create, update, or import a "skill" means a robot behavior under `./skills` unless the user explicitly asks for a Codex skill.
- Do not install robot behaviors into `~/.codex/skills` or another global directory. A `-X` flag only skips confirmation prompts; it never changes destination or scope.
- New behaviors use the public control API, begin with conservative limits, and include an offline test or test double where practical.
- Review new behavior code and parameters locally before running it on physical hardware.

## Development and verification

- Keep the core independent of voice, 01, LiveKit, and vendor Python packages.
- Develop control changes test-first when practical. Tests must not require a real camera, GPIO, I2C, servo controller, or RPC service.
- Use adapters rather than modifying or redistributing vendor code.
- After Python control changes, run the full tests and syntax checks before suggesting physical testing.
- Keep `hardware/`, `.acamp-robot.json`, secrets, recordings, and participant data out of Git. Never commit logs.

## Privacy and safeguarding

- Protect participant health and safety before project completion or entertainment value.
- Do not publish participant names, photographs, audio, video, logs, research data, account identifiers, or other identifying information without explicit authorization under camp policy.
- Treat raw `loglm` logs as potentially sensitive and prefer decoded or redacted versions for review.
- Follow all additional safeguarding, emergency, and staff-escalation requirements in `CAMP.md`.
