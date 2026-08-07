import json
import subprocess
import sys
from pathlib import Path

import pytest

from acamp_robots.research import ExperimentLog, create_project


ROOT = Path(__file__).parents[1]


def test_create_project_copies_a_runnable_local_template(tmp_path):
    destination = create_project("turn-around", root=tmp_path, template_root=ROOT / "templates")
    assert destination == tmp_path / "projects" / "turn-around"
    assert (destination / "README.md").is_file()
    assert (destination / "behavior.py").is_file()
    assert (destination / "test_behavior.py").is_file()
    assert (destination / "observations.jsonl").read_text() == ""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_behavior.py"],
        cwd=destination,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_projects_workspace_is_ignored_by_shared_git():
    assert "projects/" in (ROOT / ".gitignore").read_text().splitlines()


def test_create_project_rejects_unsafe_or_existing_names(tmp_path):
    for name in ("../escape", "has spaces", "日本語", ""):
        with pytest.raises(ValueError):
            create_project(name, root=tmp_path, template_root=ROOT / "templates")
    create_project("safe-name", root=tmp_path, template_root=ROOT / "templates")
    with pytest.raises(FileExistsError):
        create_project("safe-name", root=tmp_path, template_root=ROOT / "templates")


def test_experiment_log_appends_reproducible_anonymous_trials(tmp_path):
    log = ExperimentLog(tmp_path / "observations.jsonl", clock=lambda: "2026-08-09T01:02:03Z")
    record = log.record(
        question="Can vision improve a 180-degree turn?",
        hypothesis="Closed-loop turns will be more accurate.",
        parameters={"target_degrees": 180, "method": "camera"},
        observation="Stopped five degrees short.",
        result={"error_degrees": -5},
        artifacts=["captures/trial-01.jpg"],
    )
    assert record["recorded_at"] == "2026-08-09T01:02:03Z"
    saved = json.loads((tmp_path / "observations.jsonl").read_text())
    assert saved == record
    assert "participant" not in saved


def test_experiment_log_rejects_non_relative_artifacts(tmp_path):
    log = ExperimentLog(tmp_path / "observations.jsonl")
    with pytest.raises(ValueError, match="relative"):
        log.record(question="q", artifacts=["/tmp/private.jpg"])
