import importlib.util
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "vendor_hexapod_bridge.py"
SPEC = importlib.util.spec_from_file_location("vendor_hexapod_bridge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeThread:
    def is_alive(self):
        return True


class FakePower:
    def off(self):
        self.value = "off"

    def on(self):
        self.value = "on"


class FakeServo:
    def set_servo_angle(self, channel, angle):
        self.last = (channel, angle)


class FakeControl:
    def __init__(self):
        self.condition_thread = FakeThread()
        self.servo_power_disable = FakePower()
        self.servo = FakeServo()
        self.command_queue = []
        self.timeout = 0


def test_move_is_translated_to_freenove_command_queue():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    robot.speed(12)
    robot.move(gait=2, x=5, y=-4, angle=3)
    assert control.command_queue == ["CMD_MOVE", "2", "5", "-4", "12", "3"]
    assert control.timeout > 0


def test_head_angle_is_limited_to_servo_range():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    robot.head_vertical(999)
    assert control.servo.last == (0, 180)


def test_timed_move_stops_on_the_server_side():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    result = robot.timed_move(0.02, gait=1, x=5)
    assert result == {"accepted": True, "stop_after_seconds": 0.02}
    assert control.command_queue[2] == "5"
    time.sleep(0.05)
    assert control.command_queue == ["CMD_MOVE", "1", "0", "0", "8", "0"]
    assert robot.status()["moving"] is False


def test_timed_move_rejects_long_or_non_positive_duration():
    robot = MODULE.FreenoveDevice(FakeControl())
    with pytest.raises(ValueError):
        robot.timed_move(0)
    with pytest.raises(ValueError):
        robot.timed_move(5.1)


def test_load_device_changes_to_vendor_directory(monkeypatch, tmp_path):
    class Control(FakeControl):
        def __init__(self):
            assert Path.cwd() == tmp_path
            assert Path("point.txt").read_text() == "calibration"
            super().__init__()

    fake_module = type("FakeModule", (), {"Control": Control})
    monkeypatch.setitem(__import__("sys").modules, "control", fake_module)
    (tmp_path / "point.txt").write_text("calibration")
    device = MODULE.load_device(tmp_path)
    assert isinstance(device, MODULE.FreenoveDevice)
