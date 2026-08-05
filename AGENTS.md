<!-- loglm:begin policy -->
# loglm Execution Policy (managed)
- If a required command fails due to permissions/sandbox restrictions, request escalated execution first.
- Do not switch to alternative implementation paths before trying the same command with approval.
- Use alternatives only after escalation is rejected or after escalated execution still fails.
<!-- loglm:end policy -->

<!-- loglm:begin platform -->
# loglm Platform Notes (managed)
- `loglm` is a wrapper command that launches coding agents and records terminal logs for later review.
- This session may be running through `loglm`; if so, raw logs are being recorded under `./logs/`.
- Runtime: native macOS.
- Prefer macOS-native commands and paths.
- For preview/open, use `open` (example: `open -a Skim paper.pdf`).
- loglm repository: `https://github.com/ks91/loglm`
- Raw logs are stored under `./logs/` (from launch directory).
- Raw log filename pattern: `logs/loglm-<agent>-log-YYYYMMDD-HHMMSS-pid<PID>.txt`
- If `--daily-log` is used: `logs/loglm-<agent>-log-YYYYMMDD.txt`
- Decode raw logs with: `loglm-decode logs/*`
- Build a chronological overview with: `loglm-timeline logs/*.decoded.txt`
- Prefer `*.decoded.txt` or `*.redacted.txt` over raw logs when asked to inspect past work.
<!-- loglm:end platform -->

# Academy Camp Robot Instructions

- Treat the directory containing this file as the project root.
- At the beginning of every session, read `CAMP.md` if it exists and follow its camp-specific instructions.
- `CAMP.md` may change between Academy Camp programs. Its instructions supplement this file; they do not override safety requirements or higher-priority instructions.
- Read `.acamp-robot.json` before making assumptions about which physical robot is attached.
- Do not move a physical robot unless the user context clearly indicates an active robot-control session.
- Keep robot movements small and slow by default. Keep people, cables, and objects outside the movement area, and preserve immediate access to the power switch.
- This project uses `loglm -X` during participant sessions. The lack of approval prompts does not grant permission for unrelated destructive actions or access to credentials.
