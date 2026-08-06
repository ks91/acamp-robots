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


def test_arm_setup_uses_raspberry_pi_system_hardware_packages():
    setup = (ROOT / "scripts" / "setup.sh").read_text()
    assert 'python3 -m venv --system-site-packages "$ROOT_DIR/.venv"' in setup


def test_start_agent_marks_physical_session_as_ready():
    import tempfile

    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        (root / "scripts").mkdir()
        start = root / "scripts" / "start-agent.sh"
        start.write_text((ROOT / "scripts" / "start-agent.sh").read_text())
        prepare = root / "scripts" / "prepare-session.sh"
        prepare.write_text("#!/bin/sh\nexit 0\n")
        fake_loglm = root / "fake-loglm"
        fake_loglm.write_text("#!/bin/sh\nprintf '%s\\n' \"$ACAMP_PHYSICAL_ROBOT_READY\"\n")
        for executable in (start, prepare, fake_loglm):
            executable.chmod(0o755)
        result = subprocess.run(
            [start],
            env=os.environ | {"LOGLM_BIN": str(fake_loglm)},
            text=True,
            capture_output=True,
            check=True,
        )
        assert result.stdout.strip() == "1"
