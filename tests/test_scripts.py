import os
import subprocess
from pathlib import Path

from acamp_robots.registry import load_robot_specs


ROOT = Path(__file__).parents[1]


def test_prepare_session_delegates_without_robot_type_conditionals(tmp_path):
    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    prepare = scripts / "prepare-session.sh"
    prepare.write_text((ROOT / "scripts/prepare-session.sh").read_text())
    admin = scripts / "robot-admin.py"
    admin.write_text("from pathlib import Path\nPath(__file__).parents[1].joinpath('called').write_text('prepare')\n")
    prepare.chmod(0o755)
    result = subprocess.run([prepare], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert (root / "called").read_text() == "prepare"
    source = prepare.read_text()
    assert '== "arm"' not in source
    assert '== "hexapod"' not in source


def test_registry_owns_each_robot_preparation_command():
    specs = load_robot_specs(ROOT)
    assert specs["arm"].prepare_command == ("scripts/stop-camera-containers.sh",)
    assert specs["hexapod"].prepare_command == ("scripts/hexapod-rpc.sh", "start")


def test_setup_is_registry_driven_and_supports_generic_settings():
    setup = (ROOT / "scripts/setup.sh").read_text()
    assert "robot-admin.py" in setup
    assert "--set KEY=VALUE" in setup
    assert '== "arm"' not in setup
    assert '== "hexapod"' not in setup


def test_start_agent_marks_physical_session_as_ready():
    import tempfile

    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        (root / "scripts").mkdir()
        start = root / "scripts" / "start-agent.sh"
        start.write_text((ROOT / "scripts/start-agent.sh").read_text())
        prepare = root / "scripts" / "prepare-session.sh"
        prepare.write_text("#!/bin/sh\nexit 0\n")
        fake_loglm = root / "fake-loglm"
        fake_loglm.write_text("#!/bin/sh\nprintf '%s\\n' \"$ACAMP_PHYSICAL_ROBOT_READY\"\n")
        for executable in (start, prepare, fake_loglm):
            executable.chmod(0o755)
        result = subprocess.run(
            [start], env=os.environ | {"LOGLM_BIN": str(fake_loglm)},
            text=True, capture_output=True, check=True,
        )
        assert result.stdout.strip() == "1"
