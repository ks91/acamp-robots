from acamp_robots.controller import ArmController


def test_arm_library_is_loaded_from_external_file(tmp_path):
    library = tmp_path / "Arm_Lib.py"
    library.write_text(
        "class Arm_Device:\n"
        "    def Arm_serial_servo_write6_array(self, joints, duration):\n"
        "        return [joints, duration]\n"
        "    def Arm_serial_set_torque(self, on): return on\n"
    )
    arm = ArmController(library)
    assert arm.move_joints([90] * 6, 500) == [[90] * 6, 500]
    assert arm.stop() == 0

