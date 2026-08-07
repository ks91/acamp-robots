# Robot Skills

Place reusable participant-created robot behaviors in this directory. Use one descriptively named subdirectory per behavior, for example:

```text
skills/
└── wave/
    ├── README.md
    ├── wave.py
    └── test_wave.py
```

Skills should use the public `acamp_robots` API instead of importing vendor hardware libraries directly. Include an offline test or test double where practical, use conservative motion limits, and review the behavior before running it on physical hardware.

This directory is for robot behaviors. It is not the Codex skills directory, and its contents must not be installed into `~/.codex/skills` unless a user explicitly requests a separate Codex skill.

Start unfinished experiments under the Git-ignored `projects/` directory. Move
code here only after the member chooses to make it reusable and its privacy,
motion bounds, failure behavior, and offline tests have been reviewed.
