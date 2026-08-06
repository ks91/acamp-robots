import math
from pathlib import Path

import pytest

from acamp_robots.controller import ArmController


def make_library(path: Path):
    path.write_text(
        "class Arm_Device:\n"
        "    def __init__(self): self.calls = []; self.angles = [90] * 6\n"
        "    def Arm_serial_servo_write6_array(self, joints, duration):\n"
        "        self.angles = list(joints); self.calls.append(('move_all', list(joints), duration)); return 1\n"
        "    def Arm_serial_servo_write(self, servo, angle, duration):\n"
        "        self.angles[servo - 1] = angle; self.calls.append(('move_one', servo, angle, duration)); return 1\n"
        "    def Arm_serial_servo_read(self, servo): return self.angles[servo - 1]\n"
        "    def Arm_serial_set_torque(self, on): self.calls.append(('torque', on)); return on\n"
        "    def Arm_RGB_set(self, red, green, blue): self.calls.append(('rgb', red, green, blue)); return 1\n"
        "    def Arm_Buzzer_On(self, duration=None): self.calls.append(('buzzer_on', duration)); return 1\n"
        "    def Arm_Buzzer_Off(self): self.calls.append(('buzzer_off',)); return 1\n"
    )


@pytest.fixture
def arm(tmp_path):
    library = tmp_path / "Arm_Lib.py"
    make_library(library)
    return ArmController(library, command_interval=0)


def test_arm_exposes_the_expected_public_capabilities(arm):
    expected = {
        "status", "capabilities", "move_joint", "read_joint", "move_joints",
        "home", "stop", "rest", "torque", "led_color", "buzzer_on",
        "buzzer_off", "camera_capture", "grip_object", "tool_position",
        "move_preset", "pose_info", "target_step",
    }
    assert expected <= set(arm.capabilities())


def test_single_and_all_joint_control_are_bounded(arm):
    assert arm.move_joint(5, 265, 500) == 1
    assert arm.read_joint(5) == 265
    assert arm.move_joints([90, 90, 90, 90, 265, 30], 1000) == 1
    with pytest.raises(ValueError):
        arm.move_joint(1, 181, 500)
    with pytest.raises(ValueError):
        arm.move_joint(5, 271, 500)
    with pytest.raises(ValueError):
        arm.move_joints([90] * 5, 500)
    with pytest.raises(ValueError):
        arm.move_joints([90] * 6, 99)


def test_rest_disables_torque_and_home_uses_neutral_pose(arm):
    assert arm.home() == 1
    assert arm.device.calls[-1] == ("move_all", [90, 90, 90, 90, 90, 180], 1000)
    assert arm.rest() == 0
    assert arm.device.calls[-1] == ("torque", 0)


def test_led_and_buzzer_calls_are_bounded(arm):
    arm.led_color(20, 30, 50)
    arm.buzzer_on(5)
    arm.buzzer_off()
    assert arm.device.calls[-3:] == [
        ("rgb", 20, 30, 50), ("buzzer_on", 5), ("buzzer_off",)
    ]
    with pytest.raises(ValueError):
        arm.led_color(51, 0, 0)
    with pytest.raises(ValueError):
        arm.buzzer_on(101)


def test_grip_width_uses_the_legacy_measured_lookup_table(arm):
    result = arm.grip_object(3.0, 500)
    assert result == {"width_cm": 3.0, "gripper_angle": 134}
    assert arm.device.calls[-1] == ("move_one", 6, 134, 500)
    with pytest.raises(ValueError):
        arm.grip_object(6.5)


def test_tool_position_matches_documented_home_geometry(arm):
    position = arm.tool_position([90, 90, 90, 90, 90, 180])
    assert position["x_mm"] == pytest.approx(0, abs=0.1)
    assert position["y_mm"] == pytest.approx(0, abs=0.1)
    assert position["z_mm"] == pytest.approx(479.8, abs=0.1)
    assert position["elevation_deg"] == 90


class FakeCamera:
    def __init__(self):
        self.reads = 0
        self.settings = []

    def isOpened(self): return True
    def set(self, key, value): self.settings.append((key, value)); return True
    def read(self):
        self.reads += 1
        return True, f"frame-{self.reads}"
    def release(self): pass


def test_camera_capture_discards_a_stale_frame_and_saves_the_fresh_one(tmp_path):
    library = tmp_path / "Arm_Lib.py"
    make_library(library)
    camera = FakeCamera()
    written = {}

    def write_image(path, frame):
        written["path"] = path
        written["frame"] = frame
        Path(path).write_bytes(b"jpeg")
        return True

    arm = ArmController(
        library,
        camera_factory=lambda _index: camera,
        image_writer=write_image,
        capture_dir=tmp_path / "captures",
        command_interval=0,
    )
    result = arm.camera_capture("view.jpg")
    assert Path(result).read_bytes() == b"jpeg"
    assert written["frame"] == "frame-2"
    assert camera.reads == 2


def test_known_preset_is_named_and_unknown_presets_are_rejected(arm):
    arm.move_preset("color_view")
    assert arm.device.calls[-1][1] == [90, 120, 0, 0, 90, 30]
    with pytest.raises(ValueError):
        arm.move_preset("invented")


def test_camera_facing_and_work_area_poses_are_not_conflated(arm):
    forward = arm.pose_info("camera_forward")
    work_area = arm.pose_info("camera_work_area")
    assert forward["joints"] == [90, 65, 115, 110, 90, 120]
    assert work_area["joints"] == [90, 120, 0, 0, 90, 30]
    assert "face ahead" in forward["description"]
    assert "looking down toward the board" in work_area["description"]


def test_target_step_uses_the_legacy_eleven_section_direction(arm):
    left = arm.target_step(3)
    assert left == {"target": "adjusting", "moved": True, "base_angle": 85}
    right = arm.target_step(9)
    assert right == {"target": "adjusting", "moved": True, "base_angle": 90}
    assert arm.target_step(6) == {
        "target": "centered", "moved": False, "base_angle": 90
    }
    assert arm.target_step("not_present") == {"target": "not_present", "moved": False}
