import json
from pathlib import Path

import pytest

from acamp_robots.config import RobotConfig, default_config, load_config, save_config


ROOT = Path(__file__).parents[1]


def install_registry(path):
    (path / "robots.json").write_text((ROOT / "robots.json").read_text())


def test_round_trip_uses_generic_settings(tmp_path):
    install_registry(tmp_path)
    expected = RobotConfig(robot="hexapod", settings={"hexapod_socket": "/tmp/test.sock"})
    save_config(expected, tmp_path)
    stored = json.loads((tmp_path / ".acamp-robot.json").read_text())
    assert stored == {
        "robot": "hexapod",
        "settings": {"hexapod_socket": "/tmp/test.sock"},
    }
    loaded = load_config(tmp_path)
    assert loaded.robot == "hexapod"
    assert loaded.get("hexapod_socket") == "/tmp/test.sock"
    assert loaded.get("hexapod_server_dir") == "hardware/freenove/Code/Server"


def test_load_migrates_the_legacy_flat_device_config(tmp_path):
    install_registry(tmp_path)
    (tmp_path / ".acamp-robot.json").write_text(
        json.dumps({"robot": "arm", "arm_lib": "/vendor/Arm_Lib.py"})
    )
    loaded = load_config(tmp_path)
    assert loaded.settings == {"arm_lib": "/vendor/Arm_Lib.py"}


def test_default_config_rejects_unregistered_robot():
    with pytest.raises(ValueError, match="Unsupported robot"):
        default_config("tank")
