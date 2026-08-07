# {{PROJECT_NAME}}

This directory is a local Academy Camp research project. It is ignored by the
shared repository, so normal `git pull` operations do not replace the work here.

Keep identifying participant information out of source files, observations,
captured images, and logs. Ask nearby staff before retaining or publishing media.

## Research question

Write the question being investigated here.

## Run the offline test

```bash
../../.venv/bin/pytest -q test_behavior.py
```

## Run on the configured robot

Only do this in a prepared physical-robot session:

```bash
../../.venv/bin/python behavior.py
```

For a Hexapod choreography, edit `STEPS` in `sequence_experiment.py`. The
sequence helper accepts semantic, bounded calls, limits the complete plan to
five seconds, and issues `stop` after success, interruption, or failure.
