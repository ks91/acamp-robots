import importlib.util
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "vendor_hexapod_bridge.py"
SPEC = importlib.util.spec_from_file_location("vendor_hexapod_bridge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_bridge_protocol_version_is_explicit():
    assert MODULE.BRIDGE_PROTOCOL_VERSION == 8


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


def test_bridge_exposes_complete_semantic_motion_surface():
    capabilities = set(MODULE.FreenoveDevice(FakeControl()).capabilities())
    assert {
        "walk", "turn", "body_height", "perform", "stand", "stop", "rest"
    } <= capabilities


def test_move_is_translated_to_freenove_command_queue():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    robot.speed(10)
    robot.move(gait=2, x=5, y=-4, angle=3)
    assert control.command_queue == ["CMD_MOVE", "2", "5", "-4", "10", "3"]
    assert control.timeout > 0


def test_low_level_motion_rejects_values_outside_documented_vendor_surface():
    robot = MODULE.FreenoveDevice(FakeControl())
    for kwargs in ({"gait": 3}, {"x": 31}, {"y": -31}, {"angle": 21}):
        with pytest.raises(ValueError):
            robot.move(**kwargs)


def test_speed_uses_the_vendor_supported_two_through_ten_range():
    robot = MODULE.FreenoveDevice(FakeControl())
    assert robot.speed(2) == 2
    assert robot.speed(10) == 10
    with pytest.raises(ValueError):
        robot.speed(1)
    with pytest.raises(ValueError):
        robot.speed(11)


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


def test_walk_default_has_a_visible_fifteen_millimetre_stride():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    result = robot.walk("forward")
    robot._cancel_stop_timer()
    assert control.command_queue[3] == "15"
    assert result["step"] == 15


@pytest.mark.parametrize(
    ("direction", "expected_angle"),
    [("clockwise", "10"), ("counterclockwise", "-10")],
)
def test_turn_translates_named_rotation_without_guessing_coordinates(
    direction, expected_angle
):
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    result = robot.turn(direction)
    robot._cancel_stop_timer()
    assert control.command_queue == ["CMD_MOVE", "1", "1", "0", "8", expected_angle]
    assert result["direction"] == direction


@pytest.mark.parametrize(
    ("level", "expected_z"),
    [("low", "-15"), ("normal", "0"), ("high", "15")],
)
def test_body_height_exposes_named_bounded_postures(level, expected_z):
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    result = robot.body_height(level)
    assert control.command_queue == ["CMD_POSITION", "0", "0", expected_z]
    assert result == {"accepted": True, "height": level, "z": int(expected_z)}


def test_ball_controller_advances_when_far_and_retreats_when_too_close():
    robot = MODULE.FreenoveDevice(FakeControl())
    assert robot._ball_motion(center_x=180, radius=15)[0] > 0
    robot._reset_ball_pid()
    assert robot._ball_motion(center_x=180, radius=45)[0] < 0


def test_red_ball_detection_matches_the_proven_01_threshold_and_centroid(monkeypatch):
    calls = []

    class CV2:
        COLOR_BGR2HSV = 1
        RETR_EXTERNAL = 2
        CHAIN_APPROX_SIMPLE = 3

        @staticmethod
        def GaussianBlur(frame, kernel, sigma):
            return frame

        @staticmethod
        def cvtColor(frame, conversion):
            return frame

        @staticmethod
        def inRange(frame, low, high):
            calls.append((low, high))
            return "binary"

        @staticmethod
        def dilate(binary, kernel, iterations):
            return binary

        @staticmethod
        def findContours(binary, mode, method):
            return (["ball"], None)

        @staticmethod
        def contourArea(contour):
            return 100

        @staticmethod
        def minEnclosingCircle(contour):
            return ((999, 20), 20)

        @staticmethod
        def moments(contour):
            return {"m00": 2, "m10": 360, "m01": 40}

    robot = MODULE.FreenoveDevice(FakeControl())
    detection = robot._detect_red_ball("frame", CV2)
    assert calls == [((0, 180, 180), (5, 255, 255))]
    assert detection == (180, 20)


def test_rock_and_roll_is_a_bounded_supported_performance(monkeypatch):
    robot = MODULE.FreenoveDevice(FakeControl())
    monkeypatch.setattr(robot._performance_stop, "wait", lambda duration: False)
    result = robot.perform("rock_and_roll")
    assert result == {"accepted": True, "performance": "rock_and_roll"}
    assert robot.control.command_queue == ["CMD_ATTITUDE", "0", "0", "0"]


def test_perform_rejects_unknown_styles_with_available_choices():
    robot = MODULE.FreenoveDevice(FakeControl())
    with pytest.raises(ValueError, match="rock_and_roll"):
        robot.perform("unsafe_improvisation")


def test_walk_rejects_unknown_directions_and_large_steps():
    robot = MODULE.FreenoveDevice(FakeControl())
    with pytest.raises(ValueError):
        robot.walk("diagonal")
    with pytest.raises(ValueError):
        robot.walk("forward", step=31)


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
