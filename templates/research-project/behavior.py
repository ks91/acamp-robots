from __future__ import annotations

from pathlib import Path

from acamp_robots import create_controller, load_config
from acamp_robots.research import ExperimentLog


def run_trial(robot):
    """Replace this small example with the member's own experiment."""
    before = robot.status()
    return {"before": before, "observation": "No movement in the starter trial."}


def main():
    project = Path(__file__).resolve().parent
    root = project.parents[1]
    robot = create_controller(load_config(root), root)
    result = run_trial(robot)
    ExperimentLog(project / "observations.jsonl").record(
        question="Replace this with the research question.",
        parameters={"trial": 1},
        observation=result["observation"],
        result=result,
    )
    print(result)


if __name__ == "__main__":
    main()
