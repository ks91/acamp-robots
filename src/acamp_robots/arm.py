from __future__ import annotations

import importlib.util
import math
import time
from pathlib import Path
from typing import Any, Callable

from .config import RobotConfig
from .errors import RobotError


class ArmController:
    """Loads the vendor-provided Arm_Lib.py without redistributing it."""

    JOINT_LIMITS = ((0, 180), (0, 180), (0, 180), (0, 180), (0, 270), (0, 180))
    HOME = [90, 90, 90, 90, 90, 180]
    PRESETS = {
        "camera_forward": [90, 60, 60, 60, 90, 180],
        "camera_work_area": [90, 120, 0, 0, 90, 30],
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
    POSE_DESCRIPTIONS = {
        "camera_forward": (
            "The documented-geometry pose that makes the camera face ahead: base "
            "centered, joints 2-4 totaling 180 degrees, wrist neutral, and gripper closed."
        ),
        "camera_work_area": (
            "The legacy camera pose for looking down toward the board and inspecting "
            "colored objects; it is also the initial red-ball tracking pose."
        ),
        "color_view": "Alias of camera_work_area used for color sorting.",
        "color_grab": "Open-gripper pose above the color-sorting pickup point.",
        "color_lift": "Lifted pose holding a color-sorting object.",
        "garbage_view": "Camera pose for inspecting an item in the garbage-sorting area.",
        "garbage_grab": "Open-gripper pose at the garbage-sorting pickup point.",
        "garbage_lift": "Lifted pose holding a garbage-sorting item.",
    }
    GRIP_WIDTHS = {
        0.0: 180, 0.5: 176, 1.0: 168, 1.5: 160, 2.0: 152, 2.5: 143,
        3.0: 134, 3.5: 125, 4.0: 115, 4.5: 105, 5.0: 95, 5.5: 80,
        6.0: 57, 6.4: 0,
    }

    def __init__(
        self,
        library_path: Path,
        *,
        camera_factory: Callable[[int], Any] | None = None,
        image_writer: Callable[[str, Any], bool] | None = None,
        capture_dir: Path | None = None,
        command_interval: float = 0.1,
        sleep: Callable[[float], None] = time.sleep,
        task_stop_file: Path | None = None,
        task_beat_seconds: float = 0.5,
    ):
        if not library_path.is_file():
            raise RobotError(f"Arm_Lib.py was not found: {library_path}")
        spec = importlib.util.spec_from_file_location("acamp_vendor_arm_lib", library_path)
        if spec is None or spec.loader is None:
            raise RobotError(f"Arm_Lib.py could not be loaded: {library_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.device = module.Arm_Device()
        self._camera_factory = camera_factory
        self._image_writer = image_writer
        self._camera = None
        self.capture_dir = capture_dir or Path("/tmp/acamp-robot-captures")
        self.command_interval = max(0.0, float(command_interval))
        self._sleep = sleep
        self.task_stop_file = task_stop_file or Path("/tmp/acamp-arm-task-stop")
        self.task_beat_seconds = max(0.0, float(task_beat_seconds))
        self._torque_enabled = True

    def capabilities(self) -> list[str]:
        return sorted(
            ("buzzer_off", "buzzer_on", "camera_capture", "capabilities", "grip_object",
             "hexapod_pose", "home", "led_color", "move_joint", "move_joints", "move_preset", "pose_info", "read_joint",
             "rest", "sort_color", "sort_garbage", "status", "stop", "target_step", "tool_position", "torque")
        )

    @classmethod
    def _validate_joint(cls, joint: int, angle: int) -> tuple[int, int]:
        joint = int(joint)
        angle = int(angle)
        if not 1 <= joint <= 6:
            raise ValueError("joint must be between 1 and 6")
        low, high = cls.JOINT_LIMITS[joint - 1]
        if not low <= angle <= high:
            raise ValueError(f"joint {joint} angle must be between {low} and {high}")
        return joint, angle

    @staticmethod
    def _validate_duration(duration_ms: int) -> int:
        duration_ms = int(duration_ms)
        if not 100 <= duration_ms <= 5000:
            raise ValueError("duration_ms must be between 100 and 5000")
        return duration_ms

    def _settle_command(self, duration_ms: int):
        # Arm_Lib returns when it accepts a timed move, not when motion finishes.
        self._sleep(duration_ms / 1000.0 + self.command_interval)

    def _ensure_torque(self):
        # Each CLI call creates a fresh controller, so in-memory state cannot reveal
        # whether a previous `rest` call disabled torque in another process.
        self.torque(True)

    def move_joint(self, joint: int, angle: int, duration_ms: int = 500) -> Any:
        joint, angle = self._validate_joint(joint, angle)
        duration_ms = self._validate_duration(duration_ms)
        self._ensure_torque()
        result = self.device.Arm_serial_servo_write(
            joint, angle, duration_ms
        )
        self._settle_command(duration_ms)
        return result

    def read_joint(self, joint: int) -> Any:
        joint, _ = self._validate_joint(joint, 0)
        return self.device.Arm_serial_servo_read(joint)

    def move_joints(self, joints: list[int], duration_ms: int = 1000) -> Any:
        if len(joints) != 6:
            raise ValueError("joints must contain six angles")
        checked = [self._validate_joint(index, angle)[1] for index, angle in enumerate(joints, 1)]
        duration_ms = self._validate_duration(duration_ms)
        self._ensure_torque()
        result = self.device.Arm_serial_servo_write6_array(
            checked, duration_ms
        )
        self._settle_command(duration_ms)
        return result

    def home(self, duration_ms: int = 1000) -> Any:
        return self.move_joints(self.HOME, duration_ms)

    def torque(self, on: bool = True) -> Any:
        result = self.device.Arm_serial_set_torque(1 if on else 0)
        self._torque_enabled = bool(on)
        return result

    def stop(self) -> Any:
        self.task_stop_file.touch(exist_ok=True)
        return self.torque(False)

    def rest(self) -> Any:
        return self.stop()

    def _start_task(self):
        self.task_stop_file.unlink(missing_ok=True)

    def _check_task_cancelled(self):
        if self.task_stop_file.exists():
            raise RobotError("Arm task was stopped")

    def _task_move_preset(self, name: str, duration_ms: int = 1000):
        self._check_task_cancelled()
        self.move_preset(name, duration_ms)
        self._check_task_cancelled()

    def _task_gripper_at_pose(
        self, pose: list[int], angle: int, duration_ms: int = 500
    ):
        """Change the task gripper through the known-working six-servo API.

        Some deployed Arm_Lib/device combinations route the nominal single-servo
        ID 6 command to an arm joint. Re-sending the current task pose with only
        its sixth value changed preserves joints 1-5 while avoiding that path.
        """
        self._check_task_cancelled()
        joints = list(pose)
        joints[5] = self._validate_joint(6, angle)[1]
        self.move_joints(joints, duration_ms)
        self._check_task_cancelled()

    def _task_beat(self):
        self._check_task_cancelled()
        self._sleep(self.task_beat_seconds)
        self._check_task_cancelled()

    def _run_sort_task(self, layout: str, destination: str) -> dict[str, Any]:
        self._start_task()
        completed = []
        try:
            self._check_task_cancelled()
            self.home()
            self._check_task_cancelled()
            completed.append("home")
            grab_pose = self.PRESETS[f"{layout}_grab"]
            self._task_move_preset(f"{layout}_grab")
            completed.append("approach")
            self._task_gripper_at_pose(grab_pose, 135)
            completed.append("grasp")
            self._task_beat()
            self._task_move_preset(f"{layout}_lift")
            completed.append("lift")
            self._task_move_preset(destination)
            completed.append("carry")
            self._task_gripper_at_pose(self.PRESETS[destination], 30)
            completed.append("release")
            self._task_beat()
            self._check_task_cancelled()
            self.home()
            self._check_task_cancelled()
            completed.append("home")
        except Exception:
            self.torque(False)
            raise
        return {"accepted": True, "task": f"sort_{layout}", "destination": destination, "completed": completed}

    def sort_color(self, color: str) -> dict[str, Any]:
        """Sort the known 3 cm box after its color has been identified."""
        aliases = {"red": "red", "blue": "blue", "green": "green", "yellow": "yellow"}
        color = str(color).lower()
        if color not in aliases:
            raise ValueError("color must be red, blue, green, or yellow")
        return self._run_sort_task("color", f"color_{aliases[color]}")

    def sort_garbage(self, category: str) -> dict[str, Any]:
        """Sort the known 3 cm box after its attached item has been classified."""
        aliases = {
            "hazardous": "hazardous", "red": "hazardous",
            "recyclable": "recyclable", "blue": "recyclable",
            "kitchen": "kitchen", "green": "kitchen",
            "other": "other", "gray": "other", "grey": "other",
        }
        category = str(category).lower()
        if category not in aliases:
            raise ValueError("category must be hazardous, recyclable, kitchen, or other")
        destination = f"garbage_{aliases[category]}"
        return self._run_sort_task("garbage", destination)

    def led_color(self, red: int = 0, green: int = 0, blue: int = 0) -> Any:
        values = tuple(int(value) for value in (red, green, blue))
        if any(not 0 <= value <= 50 for value in values):
            raise ValueError("LED values must be between 0 and 50")
        return self.device.Arm_RGB_set(*values)

    def buzzer_on(self, duration_100ms: int | None = None) -> Any:
        if duration_100ms is None:
            return self.device.Arm_Buzzer_On()
        duration_100ms = int(duration_100ms)
        if not 1 <= duration_100ms <= 100:
            raise ValueError("buzzer duration must be between 1 and 100 units of 100 ms")
        return self.device.Arm_Buzzer_On(duration_100ms)

    def buzzer_off(self) -> Any:
        return self.device.Arm_Buzzer_Off()

    def _open_camera(self):
        if self._camera is not None:
            return self._camera
        if self._camera_factory is None or self._image_writer is None:
            try:
                import cv2  # type: ignore
            except ImportError as exc:
                raise RobotError("OpenCV is required for the DOFBOT camera") from exc
            self._camera_factory = cv2.VideoCapture
            self._image_writer = cv2.imwrite
            self._camera_constants = cv2
        self._camera = self._camera_factory(0)
        if not self._camera.isOpened():
            raise RobotError(
                "DOFBOT camera could not be opened; verify that the camera containers were stopped"
            )
        constants = getattr(self, "_camera_constants", None)
        if constants is not None:
            self._camera.set(constants.CAP_PROP_BUFFERSIZE, 1)
            self._camera.set(
                constants.CAP_PROP_FOURCC,
                constants.VideoWriter.fourcc("M", "J", "P", "G"),
            )
            self._camera.set(constants.CAP_PROP_BRIGHTNESS, 30)
            self._camera.set(constants.CAP_PROP_CONTRAST, 50)
        return self._camera

    def camera_capture(self, filename: str = "image.jpg") -> str:
        camera = self._open_camera()
        camera.read()  # Discard a potentially stale buffered frame.
        ok, frame = camera.read()
        if not ok or frame is None:
            raise RobotError("DOFBOT camera did not return an image")
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        destination = (self.capture_dir / (Path(str(filename)).name or "image.jpg")).resolve()
        if not self._image_writer(str(destination), frame):
            raise RobotError(f"Could not save camera image: {destination}")
        return str(destination)

    def grip_object(self, width_cm: float, duration_ms: int = 500) -> dict[str, Any]:
        width_cm = float(width_cm)
        if not 0 <= width_cm <= 6.4:
            raise ValueError("width_cm must be between 0 and 6.4")
        points = sorted(self.GRIP_WIDTHS)
        lower = max(point for point in points if point <= width_cm)
        upper = min(point for point in points if point >= width_cm)
        if lower == upper:
            angle = self.GRIP_WIDTHS[lower]
        else:
            ratio = (width_cm - lower) / (upper - lower)
            angle = round(self.GRIP_WIDTHS[lower] + ratio * (self.GRIP_WIDTHS[upper] - self.GRIP_WIDTHS[lower]))
        self.move_joint(6, angle, duration_ms)
        return {"width_cm": width_cm, "gripper_angle": angle}

    def tool_position(self, joints: list[int] | None = None) -> dict[str, float]:
        joints = joints or [int(self.read_joint(index)) for index in range(1, 7)]
        if len(joints) != 6:
            raise ValueError("joints must contain six angles")
        a1, a2, a3, a4, _a5, _a6 = [float(value) for value in joints]
        elevation = a2 + a3 + a4 - 180
        reach = (
            83.4 * math.cos(math.radians(a2))
            + 83.4 * math.cos(math.radians(a2 + a3 - 90))
            + 189.1 * math.cos(math.radians(elevation))
        )
        z = 6.0 + 13.8 + 77.0 + 27.1 + (
            83.4 * math.sin(math.radians(a2))
            + 83.4 * math.sin(math.radians(a2 + a3 - 90))
            + 189.1 * math.sin(math.radians(elevation))
        )
        return {
            "x_mm": reach * math.sin(math.radians(a1)),
            "y_mm": reach * math.cos(math.radians(a1)),
            "z_mm": z,
            "elevation_deg": elevation,
        }

    def move_preset(self, name: str, duration_ms: int = 1000) -> Any:
        try:
            joints = self.PRESETS[str(name)]
        except KeyError as exc:
            raise ValueError(f"unknown arm preset: {name}") from exc
        return self.move_joints(joints, duration_ms)

    def pose_info(self, name: str) -> dict[str, Any]:
        try:
            joints = self.PRESETS[str(name)]
        except KeyError as exc:
            raise ValueError(f"unknown arm preset: {name}") from exc
        return {
            "name": str(name),
            "joints": list(joints),
            "description": self.POSE_DESCRIPTIONS.get(str(name), "A legacy task pose."),
            "tool": self.tool_position(joints),
        }

    def hexapod_pose(
        self,
        name: str,
        base_angle: int = 90,
        gripper_angle: int | None = None,
        duration_ms: int = 1000,
    ) -> dict[str, Any]:
        """Use the legacy poses for looking at or transferring a carried box."""
        templates = {
            "look": [100, 15, 20, 90, 180],
            "grab": [65, 30, 55, 265, 30],
            "drop": [68, 30, 55, 265, 135],
        }
        name = str(name).lower()
        if name not in templates:
            raise ValueError("hexapod pose must be look, grab, or drop")
        base_angle = self._validate_joint(1, base_angle)[1]
        joints = [base_angle, *templates[name]]
        if gripper_angle is not None:
            joints[5] = self._validate_joint(6, gripper_angle)[1]
        self.move_joints(joints, duration_ms)
        return {"accepted": True, "pose": name, "joints": joints}

    def target_step(self, section: int | str, duration_ms: int = 300) -> dict[str, Any]:
        """Move the base one bounded step toward an 11-section visual target."""
        if str(section) == "not_present":
            return {"target": "not_present", "moved": False}
        section = int(section)
        if not 1 <= section <= 11:
            raise ValueError("section must be between 1 and 11 or 'not_present'")
        current = int(self.read_joint(1))
        delta = -5 if section < 6 else 5 if section > 6 else 0
        if delta == 0:
            return {"target": "centered", "moved": False, "base_angle": current}
        angle = max(0, min(180, current + delta))
        if angle != current:
            self.move_joint(1, angle, duration_ms)
        return {"target": "adjusting", "moved": angle != current, "base_angle": angle}

    def status(self) -> dict[str, Any]:
        return {
            "robot": "arm",
            "ready": True,
            "joints": [self.read_joint(index) for index in range(1, 7)],
            "capabilities": self.capabilities(),
        }

    def call(self, method: str, *args: Any) -> Any:
        if method.startswith("_") or method not in self.capabilities():
            raise RobotError(f"Unknown arm method: {method}")
        return getattr(self, method)(*args)


def create_controller(config: RobotConfig, root: Path) -> ArmController:
    path = Path(config.get("arm_lib", "hardware/Arm_Lib.py"))
    return ArmController(path if path.is_absolute() else root / path)
