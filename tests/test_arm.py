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


def test_motion_reenables_torque_after_rest(arm):
    arm.rest()
    arm.home()
    assert arm.device.calls[-2:] == [
        ("torque", 1),
        ("move_all", [90, 90, 90, 90, 90, 180], 1000),
    ]


def test_fresh_controller_always_enables_torque_before_motion(arm):
    arm.home()
    assert arm.device.calls[-2][0:2] == ("torque", 1)


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
    assert arm.grip_object(6.4)["gripper_angle"] == 0
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


def test_all_legacy_sorting_coordinates_are_preserved(arm):
    expected = {
        "color_view": [90, 120, 0, 0, 90, 30],
        "color_grab": [90, 43, 36, 40, 90, 30],
        "color_lift": [90, 80, 35, 40, 90, 135],
        "color_red": [117, 19, 66, 56, 90, 135],
        "color_blue": [44, 66, 20, 28, 90, 135],
        "color_green": [136, 66, 20, 29, 90, 135],
        "color_yellow": [65, 22, 64, 56, 90, 135],
        "garbage_view": [90, 90, 15, 20, 90, 30],
        "garbage_grab": [90, 40, 30, 67, 265, 30],
        "garbage_lift": [90, 80, 50, 50, 265, 135],
        "garbage_hazardous": [45, 80, 35, 40, 265, 135],
        "garbage_recyclable": [27, 110, 0, 40, 265, 135],
        "garbage_kitchen": [152, 110, 0, 40, 265, 135],
        "garbage_other": [137, 80, 35, 40, 265, 135],
    }
    assert {name: arm.PRESETS[name] for name in expected} == expected


def test_camera_facing_and_work_area_poses_are_not_conflated(arm):
    forward = arm.pose_info("camera_forward")
    work_area = arm.pose_info("camera_work_area")
    assert forward["joints"] == [90, 60, 60, 60, 90, 180]
    assert forward["tool"]["elevation_deg"] == 0
    assert work_area["joints"] == [90, 120, 0, 0, 90, 30]
    assert "face ahead" in forward["description"]
    assert "looking down toward the board" in work_area["description"]


def test_hexapod_transfer_poses_preserve_requested_base_and_grip(arm):
    result = arm.hexapod_pose("look", base_angle=105, gripper_angle=180)
    assert result["joints"] == [105, 100, 15, 20, 90, 180]
    assert arm.device.calls[-1] == (
        "move_all", [105, 100, 15, 20, 90, 180], 1000
    )
    result = arm.hexapod_pose("grab", base_angle=75)
    assert result["joints"] == [75, 65, 30, 55, 265, 30]


def test_target_step_uses_the_legacy_eleven_section_direction(arm):
    left = arm.target_step(3)
    assert left == {"target": "adjusting", "moved": True, "base_angle": 85}
    right = arm.target_step(9)
    assert right == {"target": "adjusting", "moved": True, "base_angle": 90}
    assert arm.target_step(6) == {
        "target": "centered", "moved": False, "base_angle": 90
    }
    assert arm.target_step("not_present") == {"target": "not_present", "moved": False}
