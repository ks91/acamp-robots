import importlib.util
from pathlib import Path


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
