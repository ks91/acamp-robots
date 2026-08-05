import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]


def run_prepare(tmp_path, robot):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / ".acamp-robot.json").write_text(json.dumps({"robot": robot}))
    source = (ROOT / "scripts" / "prepare-session.sh").read_text()
    (root / "scripts" / "prepare-session.sh").write_text(source)
    marker = root / "called"
    target = "stop-camera-containers.sh" if robot == "arm" else "hexapod-rpc.sh"
    script = root / "scripts" / target
    script.write_text(f"#!/bin/sh\necho \"$*\" > '{marker}'\n")
    os.chmod(root / "scripts" / "prepare-session.sh", 0o755)
    os.chmod(script, 0o755)
    subprocess.run([root / "scripts" / "prepare-session.sh"], check=True)
    return marker.read_text().strip()


def test_arm_preparation_stops_camera_container(tmp_path):
    assert run_prepare(tmp_path, "arm") == ""


def test_hexapod_preparation_starts_rpc(tmp_path):
    assert run_prepare(tmp_path, "hexapod") == "start"

