# Robot instruction modules

`AGENTS.md` routes agents to `.agents/common.md` and exactly one robot module selected through `robots.json` and `.acamp-robot.json`.

To add a robot:

1. Add one entry to `robots.json` with its controller factory, instruction file, preparation command, virtual-environment policy, defaults, and setup note.
2. Implement the controller factory named by `controller_factory` using the common controller interface (`status`, `call`, and `stop` at minimum).
3. Add the preparation command and keep it idempotent.
4. Add `.agents/robots/<name>.md` containing only that robot's body, semantics, hardware path, and failure procedures.
5. Add offline controller, setup, preparation, instruction-routing, and participant-language tests.
6. Update the public README and perform a documented physical acceptance test before declaring support.

Do not add robot-specific rules back to root `AGENTS.md` or `.agents/common.md`.
