import pytest

from acamp_robots.config import RobotConfig, load_config, save_config


def test_round_trip(tmp_path):
    expected = RobotConfig(robot="hexapod", hexapod_socket="/tmp/test.sock")
    save_config(expected, tmp_path)
    assert load_config(tmp_path) == expected


def test_rejects_unknown_robot():
    with pytest.raises(ValueError):
        RobotConfig(robot="tank")

