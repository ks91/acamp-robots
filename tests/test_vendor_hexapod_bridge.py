import importlib.util
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "vendor_hexapod_bridge.py"
SPEC = importlib.util.spec_from_file_location("vendor_hexapod_bridge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_bridge_protocol_version_is_explicit():
    assert MODULE.BRIDGE_PROTOCOL_VERSION == 6


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


def test_bridge_preserves_the_legacy_hexapod_api_surface():
    expected = {
        "connect", "disconnect", "servopower", "speed", "move", "stop",
        "balance", "position", "attitude", "head_vertical", "head_horizontal",
        "buzzer_on", "buzzer_off", "led_mode", "led_color", "camera_capture",
        "sonic", "power", "ball_start", "ball_stop", "ball_state",
        "set_leg_position", "set_leg_positions", "set_leg_servo_angles",
        "set_leg_servo_angles_all", "set_leg_joint_angles",
        "set_leg_joint_angles_all", "rest",
    }
    assert expected <= set(MODULE.FreenoveDevice(FakeControl()).capabilities())


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


def test_stand_enables_power_and_requests_neutral_posture():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    result = robot.stand()
    assert result == {"accepted": True, "posture": "stand"}
    assert control.servo_power_disable.value == "off"
    assert control.command_queue == ["CMD_POSITION", "0", "0", "0"]
    assert robot.status()["servo_power"] is True


def test_rest_stops_motion_and_disables_servo_power():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    robot.servopower(True)
    result = robot.rest()
    assert result == {"accepted": True, "servo_power": False}
    assert control.command_queue == ["CMD_MOVE", "1", "0", "0", "8", "0"]
    assert control.servo_power_disable.value == "on"
    assert robot.status()["servo_power"] is False


def test_rest_does_not_initialize_hardware_when_already_resting():
    robot = MODULE.FreenoveDevice(server_dir="/vendor/not-needed")
    assert robot.rest() == {
        "accepted": True,
        "servo_power": False,
        "already_resting": True,
    }
    assert robot.hardware_initialized is False


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


@pytest.mark.parametrize(
    ("direction", "expected_x", "expected_y"),
    [
        ("forward", "0", "5"),
        ("backward", "0", "-5"),
        ("left", "-5", "0"),
        ("right", "5", "0"),
    ],
)
def test_walk_translates_named_directions_to_vendor_coordinates(
    direction, expected_x, expected_y
):
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    result = robot.walk(direction, duration=1, step=5)
    robot._cancel_stop_timer()
    assert control.command_queue == [
        "CMD_MOVE",
        "1",
        expected_x,
        expected_y,
        "8",
        "0",
    ]
    assert result["direction"] == direction


def test_walk_rejects_unknown_directions_and_large_steps():
    robot = MODULE.FreenoveDevice(FakeControl())
    with pytest.raises(ValueError):
        robot.walk("diagonal")
    with pytest.raises(ValueError):
        robot.walk("forward", step=11)


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
