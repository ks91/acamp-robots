import importlib.util
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "vendor_hexapod_bridge.py"
SPEC = importlib.util.spec_from_file_location("vendor_hexapod_bridge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_bridge_protocol_version_is_explicit():
    assert MODULE.BRIDGE_PROTOCOL_VERSION == 11


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


class FakeIMUSensor:
    def __init__(self):
        self.gyro_z = 0.0

    def get_accel_data(self):
        return {"x": 0.0, "y": 0.0, "z": 9.8}

    def get_gyro_data(self):
        return {"x": 1.0, "y": 2.0, "z": self.gyro_z}

    def get_temp(self):
        return 24.5


class FakeIMU:
    def __init__(self):
        self.sensor = FakeIMUSensor()
        self.error_gyro_data = {"x": 0.0, "y": 0.0, "z": 0.0}


class FakeControl:
    def __init__(self):
        self.condition_thread = FakeThread()
        self.servo_power_disable = FakePower()
        self.servo = FakeServo()
        self.command_queue = []
        self.timeout = 0
        self.leg_positions = [[140, 0, -30] for _ in range(6)]
        self.calibration_angles = [[0, 0, 0] for _ in range(6)]
        self.set_leg_angles_calls = 0
        self.imu = FakeIMU()

    def check_point_validity(self):
        return True

    def set_leg_angles(self):
        self.set_leg_angles_calls += 1


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
        "walk", "turn", "body_height", "perform", "lift_leg", "lower_leg",
        "lower_all_legs", "imu_read", "tilt_read", "turn_by", "head_pose",
        "leg_positions", "distance_read", "stand", "stop", "rest"
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


def test_imu_read_returns_averaged_values_with_explicit_units():
    robot = MODULE.FreenoveDevice(FakeControl())
    result = robot.imu_read(samples=2)
    assert result == {
        "acceleration_m_s2": {"x": 0.0, "y": 0.0, "z": 9.8},
        "angular_velocity_deg_s": {"x": 1.0, "y": 2.0, "z": 0.0},
        "temperature_c": 24.5,
        "samples": 2,
    }


def test_tilt_read_uses_acceleration_without_claiming_a_yaw_heading():
    robot = MODULE.FreenoveDevice(FakeControl())
    result = robot.tilt_read(samples=1)
    assert result["roll_degrees"] == pytest.approx(0)
    assert result["pitch_degrees"] == pytest.approx(0)
    assert result["yaw_available"] is False


def test_turn_by_integrates_z_gyro_and_stops_near_requested_relative_angle():
    control = FakeControl()
    control.imu.sensor.gyro_z = 100.0
    robot = MODULE.FreenoveDevice(control)

    class Clock:
        value = 0.0

        def __call__(self):
            return self.value

        def sleep(self, duration):
            self.value += duration

    clock = Clock()
    robot._monotonic = clock
    robot._sleep = clock.sleep
    result = robot.turn_by("clockwise", 90, max_seconds=2, sample_interval=0.1)
    assert result["reached"] is True
    assert result["measured_degrees"] == pytest.approx(90)
    assert result["direction"] == "clockwise"
    assert control.command_queue == ["CMD_MOVE", "1", "0", "0", "8", "0"]


def test_turn_by_times_out_and_stops_when_gyro_does_not_observe_rotation():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)

    class Clock:
        value = 0.0

        def __call__(self):
            return self.value

        def sleep(self, duration):
            self.value += duration

    clock = Clock()
    robot._monotonic = clock
    robot._sleep = clock.sleep
    result = robot.turn_by("counterclockwise", 180, max_seconds=0.3, sample_interval=0.1)
    assert result["reached"] is False
    assert result["reason"] == "timeout"
    assert control.command_queue == ["CMD_MOVE", "1", "0", "0", "8", "0"]


def test_turn_by_reports_external_stop_as_cancellation():
    control = FakeControl()
    control.imu.sensor.gyro_z = 20
    robot = MODULE.FreenoveDevice(control)

    class Clock:
        value = 0.0

        def __call__(self):
            return self.value

        def sleep(self, duration):
            self.value += duration
            robot.stop()

    clock = Clock()
    robot._monotonic = clock
    robot._sleep = clock.sleep
    result = robot.turn_by("clockwise", 180, max_seconds=2, sample_interval=0.1)
    assert result["reached"] is False
    assert result["reason"] == "cancelled"


def test_turn_by_rejects_unbounded_angles_and_runtime():
    robot = MODULE.FreenoveDevice(FakeControl())
    for degrees in (0, 361):
        with pytest.raises(ValueError, match="degrees"):
            robot.turn_by("clockwise", degrees)
    with pytest.raises(ValueError, match="max_seconds"):
        robot.turn_by("clockwise", 90, max_seconds=5.1)


def test_named_head_poses_and_leg_position_observation_are_available():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    assert robot.head_pose("left") == {
        "accepted": True, "pose": "left", "horizontal": 120, "vertical": 90
    }
    positions = robot.leg_positions()
    assert positions == [[140, 0, -30] for _ in range(6)]
    positions[0][0] = 999
    assert control.leg_positions[0][0] == 140


def test_distance_read_reports_robust_ultrasonic_summary(monkeypatch):
    class Ultrasonic:
        readings = iter([31.0, 29.0, 100.0, None, 30.0])

        def get_distance(self):
            return next(self.readings)

    robot = MODULE.FreenoveDevice(FakeControl())
    robot._peripherals["ultrasonic"] = Ultrasonic()
    monkeypatch.setattr(robot, "_sleep", lambda duration: None)
    result = robot.distance_read(samples=5, interval=0.01)
    assert result == {
        "unit": "cm",
        "median": 30.5,
        "minimum": 29.0,
        "maximum": 100.0,
        "readings": [31.0, 29.0, 100.0, 30.0],
        "samples_requested": 5,
        "samples_valid": 4,
    }


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


def test_lift_leg_maps_human_leg_one_to_vendor_index_zero_and_moves_only_it():
    control = FakeControl()
    before = [list(position) for position in control.leg_positions]
    robot = MODULE.FreenoveDevice(control)
    result = robot.lift_leg(1)
    assert result == {"accepted": True, "leg": 1, "lift": 30}
    assert control.leg_positions[0] == [140, 0, 0]
    assert control.leg_positions[1:] == before[1:]
    assert control.set_leg_angles_calls == 1


def test_lower_leg_restores_the_position_saved_before_lifting():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    robot.lift_leg(6, 20)
    result = robot.lower_leg(6)
    assert result == {"accepted": True, "leg": 6, "lowered": True}
    assert control.leg_positions[5] == [140, 0, -30]


def test_leg_semantics_reject_bad_numbers_and_unsafe_lift_sizes():
    robot = MODULE.FreenoveDevice(FakeControl())
    for leg in (0, 7):
        with pytest.raises(ValueError, match="leg must be between 1 and 6"):
            robot.lift_leg(leg)
    for lift in (4, 41):
        with pytest.raises(ValueError, match="lift must be between 5 and 40"):
            robot.lift_leg(1, lift)


def test_lower_all_legs_restores_every_saved_position():
    control = FakeControl()
    robot = MODULE.FreenoveDevice(control)
    robot.lift_leg(1)
    robot.lift_leg(4, 20)
    assert robot.lower_all_legs() == {"accepted": True, "lowered_legs": [1, 4]}
    assert control.leg_positions == [[140, 0, -30] for _ in range(6)]


def test_ball_controller_advances_when_far_and_retreats_when_too_close():
    robot = MODULE.FreenoveDevice(FakeControl())
    assert robot._ball_motion(center_x=180, radius=15)[0] > 0
    robot._reset_ball_pid()
    assert robot._ball_motion(center_x=180, radius=45)[0] < 0


def test_ball_controller_has_stable_distance_and_center_deadbands():
    robot = MODULE.FreenoveDevice(FakeControl())
    assert robot._ball_motion(center_x=180, radius=22.5) == (0, 0)
    robot._reset_ball_pid()
    assert robot._ball_motion(center_x=185, radius=22.5) == (0, 0)


def test_ball_tracker_bridges_three_dropped_frames_before_stopping():
    robot = MODULE.FreenoveDevice(FakeControl())
    first = robot._update_ball_observation((180, 15), now=10.0)
    assert first[0] > 0
    assert robot._update_ball_observation(None, now=10.1) == first
    assert robot._update_ball_observation(None, now=10.2) == first
    assert robot._update_ball_observation(None, now=10.3) == first
    assert robot._update_ball_observation(None, now=10.4) == (0, 0)
    assert robot.status()["ball_tracking"]["missed_frames"] == 4


def test_ball_tracker_smooths_noisy_centers_and_reports_telemetry():
    robot = MODULE.FreenoveDevice(FakeControl())
    robot._update_ball_observation((140, 20), now=20.0)
    robot._update_ball_observation((220, 24), now=20.04)
    telemetry = robot.status()["ball_tracking"]
    assert 140 < telemetry["center_x"] < 220
    assert 20 < telemetry["radius"] < 24
    assert telemetry["frame_interval_ms"] == pytest.approx(40)
    assert telemetry["missed_frames"] == 0


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
