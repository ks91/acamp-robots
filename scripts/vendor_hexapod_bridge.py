#!/usr/bin/env python3
"""Small adapter around the separately installed Freenove server code."""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import queue
import socketserver
import statistics
import sys
import threading
import time
from pathlib import Path

BRIDGE_PROTOCOL_VERSION = 14


class _TrackingPID:
    """The ball-following controller used by the proven 01 implementation."""

    def __init__(self, p=0.0, i=0.0, d=0.0):
        self.set_point = 0.0
        self.kp = p
        self.ki = i
        self.kd = d
        self.last_error = 0.0
        self.i_error = 0.0
        self.i_saturation = 10.0

    def compute(self, feedback):
        error = self.set_point - feedback
        self.i_error = max(
            -self.i_saturation, min(self.i_saturation, self.i_error + error)
        )
        output = (
            self.kp * error
            + self.ki * self.i_error
            + self.kd * (error - self.last_error)
        )
        self.last_error = error
        return -output


class FreenoveDevice:
    """Stable API over Freenove's command-queue based Control class."""

    _LEG_CHANNELS = [
        (15, 14, 13),
        (12, 11, 10),
        (9, 8, 31),
        (22, 23, 27),
        (19, 20, 21),
        (16, 17, 18),
    ]

    _PERFORMANCES = {
        "nod": (
            ("head_vertical", (78,), 0.15),
            ("head_vertical", (100,), 0.15),
            ("head_vertical", (90,), 0.10),
        ),
        "sway": (
            ("position", (-8, 0, 0), 0.16),
            ("attitude", (-7, 0, -4), 0.16),
            ("position", (8, 0, 0), 0.16),
            ("attitude", (7, 0, 4), 0.16),
        ),
        "bounce": (
            ("position", (0, 0, 8), 0.14),
            ("position", (0, 0, -5), 0.14),
            ("position", (0, 0, 7), 0.14),
        ),
        "curious": (
            ("head_horizontal", (70,), 0.18),
            ("attitude", (0, 5, -5), 0.18),
            ("head_horizontal", (110,), 0.18),
            ("attitude", (0, -3, 5), 0.18),
        ),
        "happy": (
            ("attitude", (7, 0, 6), 0.15),
            ("attitude", (-7, 0, -6), 0.15),
            ("attitude", (6, 0, 5), 0.15),
        ),
        "thinking": (
            ("head_horizontal", (65,), 0.22),
            ("head_horizontal", (115,), 0.22),
            ("head_horizontal", (85,), 0.15),
        ),
        "rock_and_roll": (
            ("position", (-10, 0, 5), 0.15),
            ("attitude", (-8, 4, -7), 0.15),
            ("head_horizontal", (65,), 0.12),
            ("position", (10, 0, -3), 0.15),
            ("attitude", (8, -4, 7), 0.15),
            ("head_horizontal", (115,), 0.12),
            ("position", (-8, 0, 6), 0.14),
            ("attitude", (-6, 3, -5), 0.14),
            ("position", (8, 0, -3), 0.14),
            ("attitude", (6, -3, 5), 0.14),
        ),
    }
    _BALL_SMOOTHING_ALPHA = 0.35
    _BALL_LOSS_GRACE_FRAMES = 3

    def __init__(self, control=None, server_dir=None):
        self.control = control
        self.server_dir = Path(server_dir or Path.cwd()).resolve()
        self.move_speed = 8
        self._lock = threading.RLock()
        self._stop_timer = None
        self._moving = False
        self._servo_power = None
        self._last_command = None
        self._peripherals = {}
        self._led_thread = None
        self._ball_thread = None
        self._ball_stop = threading.Event()
        self._ball_active = False
        self._ball_tracking = False
        self._reset_ball_pid()
        self._performance_stop = threading.Event()
        self._performance_lock = threading.Lock()
        self._lifted_leg_positions = {}
        self._monotonic = time.monotonic
        self._sleep = time.sleep
        self._turn_by_stop = threading.Event()
        self._turn_by_thread = None
        self._turn_by_state = None

    @property
    def hardware_initialized(self):
        return self.control is not None

    def attach_control(self, control):
        with self._lock:
            if self.control is None:
                self.control = control
                if not self.control.condition_thread.is_alive():
                    self.control.condition_thread.start()

    def servopower(self, on=True):
        with self._lock:
            if on:
                self.control.servo_power_disable.off()
            else:
                self.stop()
                self.control.servo_power_disable.on()
            self._servo_power = bool(on)

    def stand(self):
        """Enable servo power and request the vendor neutral standing posture."""
        with self._lock:
            self.servopower(True)
            self.position(0, 0, 0)
        return {"accepted": True, "posture": "stand"}

    def rest(self):
        """Stop all motion and disable servo power without initializing hardware."""
        if not self.hardware_initialized:
            self._servo_power = False
            return {"accepted": True, "servo_power": False, "already_resting": True}
        self.servopower(False)
        return {"accepted": True, "servo_power": False}

    def emergency_stop(self):
        """Cancel every activity, stop gait, and remove servo torque."""
        self._ball_stop.set()
        self._performance_stop.set()
        self._turn_by_stop.set()
        if not self.hardware_initialized:
            self._servo_power = False
            return {"accepted": True, "servo_power": False, "already_resting": True}
        self.servopower(False)
        return {"accepted": True, "servo_power": False}

    def connect(self):
        if not self.control.condition_thread.is_alive():
            self.control.condition_thread.start()
        return {"connected": True}

    def disconnect(self):
        self.ball_stop()
        self.servopower(False)
        camera = self._peripherals.get("camera")
        if camera is not None and getattr(camera, "streaming", False):
            camera.stop_stream()
        return {"connected": False}

    def _peripheral(self, key, module_name, class_name):
        with self._lock:
            if key not in self._peripherals:
                sys.path.insert(0, str(self.server_dir))
                os.chdir(self.server_dir)
                module = importlib.import_module(module_name)
                self._peripherals[key] = getattr(module, class_name)()
            return self._peripherals[key]

    def speed(self, tempo=8):
        with self._lock:
            tempo = int(tempo)
            if not 2 <= tempo <= 10:
                raise ValueError("tempo must be between 2 and 10")
            self.move_speed = tempo
            return self.move_speed

    def _queue(self, *values):
        self.control.command_queue = [str(value) for value in values]
        self.control.timeout = time.time()
        self._last_command = self.control.command_queue.copy()

    def _cancel_stop_timer(self):
        if self._stop_timer is not None:
            self._stop_timer.cancel()
            self._stop_timer = None

    def move(self, gait=1, x=0, y=0, angle=0):
        gait, x, y, angle = int(gait), int(x), int(y), int(angle)
        if gait not in (1, 2):
            raise ValueError("gait must be 1 or 2")
        if not -30 <= x <= 30 or not -30 <= y <= 30:
            raise ValueError("x and y must be between -30 and 30")
        if not -20 <= angle <= 20:
            raise ValueError("angle must be between -20 and 20")
        external_motion = threading.current_thread() is not self._ball_thread
        if threading.current_thread() is not self._turn_by_thread:
            self._turn_by_stop.set()
        if external_motion and self._ball_active:
            with self._lock:
                self._ball_active = False
                self._ball_tracking = False
                self._ball_stop.set()
            if self._ball_thread is not None and self._ball_thread.is_alive():
                self._ball_thread.join(timeout=2.5)
        with self._lock:
            self._cancel_stop_timer()
            self._moving = any(value != 0 for value in (x, y, angle))
            self._queue("CMD_MOVE", gait, x, y, self.move_speed, angle)

    def stop(self):
        self._performance_stop.set()
        self._turn_by_stop.set()
        with self._lock:
            self._cancel_stop_timer()
            self._moving = False
            self._queue("CMD_MOVE", 1, 0, 0, self.move_speed, 0)

    def timed_move(self, duration, gait=1, x=0, y=0, angle=0):
        duration = float(duration)
        if not 0 < duration <= 30:
            raise ValueError("duration must be greater than 0 and at most 30 seconds")
        with self._lock:
            self.move(gait=gait, x=x, y=y, angle=angle)
            self._stop_timer = threading.Timer(duration, self.stop)
            self._stop_timer.daemon = True
            self._stop_timer.start()
        return {"accepted": True, "stop_after_seconds": duration}

    def walk(self, direction, duration=1.0, step=15, gait=1):
        """Walk briefly using human-readable directions, not vendor coordinates."""
        direction = str(direction).lower()
        vectors = {
            "forward": (0, 1),
            "backward": (0, -1),
            "left": (-1, 0),
            "right": (1, 0),
        }
        if direction not in vectors:
            raise ValueError("direction must be forward, backward, left, or right")
        step = int(step)
        if not 1 <= step <= 30:
            raise ValueError("step must be between 1 and 30")
        x_sign, y_sign = vectors[direction]
        result = self.timed_move(
            duration,
            gait=int(gait),
            x=x_sign * step,
            y=y_sign * step,
            angle=0,
        )
        result["direction"] = direction
        result["step"] = step
        return result

    def turn(self, direction, duration=1.0, angle=10, gait=1):
        """Turn briefly using names whose meaning is independent of vendor axes."""
        direction = str(direction).lower().replace("-", "").replace("_", "")
        signs = {
            "clockwise": 1,
            "cw": 1,
            "counterclockwise": -1,
            "anticlockwise": -1,
            "ccw": -1,
        }
        if direction not in signs:
            raise ValueError("direction must be clockwise or counterclockwise")
        angle = int(angle)
        if not 1 <= angle <= 20:
            raise ValueError("angle must be between 1 and 20")
        canonical = "clockwise" if signs[direction] > 0 else "counterclockwise"
        # Freenove needs a non-zero translation component to execute rotation.
        result = self.timed_move(
            duration, gait=int(gait), x=1, y=0, angle=signs[direction] * angle
        )
        result.update({"direction": canonical, "angle": angle})
        return result

    def imu_read(self, samples=1):
        """Read calibrated-unit acceleration, angular velocity, and temperature."""
        samples = int(samples)
        if not 1 <= samples <= 50:
            raise ValueError("samples must be between 1 and 50")
        totals = {
            "accel": {axis: 0.0 for axis in "xyz"},
            "gyro": {axis: 0.0 for axis in "xyz"},
            "temperature": 0.0,
        }
        sensor = self.control.imu.sensor
        with self._lock:
            for _ in range(samples):
                accel = sensor.get_accel_data()
                gyro = sensor.get_gyro_data()
                for axis in "xyz":
                    totals["accel"][axis] += float(accel[axis])
                    totals["gyro"][axis] += float(gyro[axis])
                totals["temperature"] += float(sensor.get_temp())
        return {
            "acceleration_m_s2": {
                axis: round(totals["accel"][axis] / samples, 4) for axis in "xyz"
            },
            "angular_velocity_deg_s": {
                axis: round(totals["gyro"][axis] / samples, 4) for axis in "xyz"
            },
            "temperature_c": round(totals["temperature"] / samples, 2),
            "samples": samples,
        }

    def tilt_read(self, samples=5):
        """Estimate roll and pitch from gravity; MPU6050 cannot give compass yaw."""
        reading = self.imu_read(samples)
        accel = reading["acceleration_m_s2"]
        roll = math.degrees(math.atan2(accel["y"], accel["z"]))
        pitch = math.degrees(
            math.atan2(-accel["x"], math.hypot(accel["y"], accel["z"]))
        )
        return {
            "roll_degrees": round(roll, 2),
            "pitch_degrees": round(pitch, 2),
            "yaw_available": False,
            "source": "accelerometer",
        }

    def turn_by(
        self,
        direction,
        degrees,
        angle=10,
        gait=1,
        max_seconds=None,
        sample_interval=0.02,
    ):
        """Turn through a measured relative angle by integrating Z-axis gyro rate."""
        normalized = str(direction).lower().replace("-", "").replace("_", "")
        signs = {
            "clockwise": 1,
            "cw": 1,
            "counterclockwise": -1,
            "anticlockwise": -1,
            "ccw": -1,
        }
        if normalized not in signs:
            raise ValueError("direction must be clockwise or counterclockwise")
        degrees = float(degrees)
        if not 0 < degrees <= 360:
            raise ValueError("degrees must be greater than 0 and at most 360")
        if max_seconds is None:
            max_seconds = max(5.0, min(30.0, degrees / 15.0))
        max_seconds = float(max_seconds)
        if not 0 < max_seconds <= 30:
            raise ValueError("max_seconds must be greater than 0 and at most 30")
        sample_interval = float(sample_interval)
        if not 0.01 <= sample_interval <= 0.1:
            raise ValueError("sample_interval must be between 0.01 and 0.1")
        angle = int(angle)
        if not 3 <= angle <= 20:
            raise ValueError("angle must be between 3 and 20")
        gait = int(gait)
        if gait not in (1, 2):
            raise ValueError("gait must be 1 or 2")

        if self._ball_active:
            self.ball_stop()
        self.stop()
        self._turn_by_stop.clear()
        self._turn_by_thread = threading.current_thread()
        canonical = "clockwise" if signs[normalized] > 0 else "counterclockwise"
        sensor = self.control.imu.sensor
        gyro_bias = float(getattr(self.control.imu, "error_gyro_data", {}).get("z", 0))
        measured = 0.0
        start = self._monotonic()
        reached = False
        reason = "timeout"
        self._turn_by_state = {
            "active": True,
            "direction": canonical,
            "target_degrees": degrees,
            "measured_degrees": 0.0,
        }
        try:
            last = start
            self.move(gait=gait, x=1, y=0, angle=signs[normalized] * angle)
            while not self._turn_by_stop.is_set():
                self._sleep(sample_interval)
                now = self._monotonic()
                elapsed = now - start
                rate = abs(float(sensor.get_gyro_data()["z"]) - gyro_bias)
                if rate >= 1.5:
                    measured += min(
                        rate * max(0.0, now - last), degrees - measured
                    )
                last = now
                self._turn_by_state["measured_degrees"] = round(measured, 2)
                if measured >= degrees:
                    reached = True
                    reason = "target_reached"
                    break
                if elapsed >= max_seconds:
                    break
                remaining = degrees - measured
                if remaining < 30:
                    reduced = max(3, min(angle, round(angle * remaining / 30)))
                    self.move(
                        gait=gait, x=1, y=0, angle=signs[normalized] * reduced
                    )
            if self._turn_by_stop.is_set() and not reached:
                reason = "cancelled"
        finally:
            self.stop()
            elapsed = self._monotonic() - start
            self._turn_by_thread = None
            self._turn_by_state = {
                "active": False,
                "direction": canonical,
                "target_degrees": degrees,
                "measured_degrees": round(measured, 2),
                "reached": reached,
                "reason": reason,
            }
        return {
            "accepted": True,
            "direction": canonical,
            "target_degrees": degrees,
            "measured_degrees": round(measured, 2),
            "elapsed_seconds": round(elapsed, 3),
            "reached": reached,
            "reason": reason,
            "measurement": "integrated_mpu6050_z_gyro",
        }

    def body_height(self, level="normal"):
        """Set one of three tested body heights without exposing coordinate signs."""
        heights = {"low": -15, "normal": 0, "high": 15}
        level = str(level).lower()
        if level not in heights:
            raise ValueError("height must be low, normal, or high")
        z = heights[level]
        self.position(0, 0, z)
        return {"accepted": True, "height": level, "z": z}

    def perform(self, style="happy"):
        """Run a short, bounded, interruptible whole-body performance."""
        style = str(style).lower().strip().replace("-", "_").replace(" ", "_")
        aliases = {"rock": "rock_and_roll", "rocknroll": "rock_and_roll"}
        style = aliases.get(style, style)
        if style not in self._PERFORMANCES:
            choices = ", ".join(sorted(self._PERFORMANCES))
            raise ValueError(f"unknown performance; choose one of: {choices}")
        if not self._performance_lock.acquire(blocking=False):
            raise RuntimeError("another performance is already running")
        try:
            if self._ball_active:
                self.ball_stop()
            self.stop()
            self._performance_stop.clear()
            for method, args, pause in self._PERFORMANCES[style]:
                if self._performance_stop.is_set():
                    return {"accepted": True, "performance": style, "cancelled": True}
                getattr(self, method)(*args)
                if self._performance_stop.wait(pause):
                    return {"accepted": True, "performance": style, "cancelled": True}
            self.position(0, 0, 0)
            self.attitude(0, 0, 0)
            self.head_horizontal(90)
            self.head_vertical(90)
            return {"accepted": True, "performance": style}
        finally:
            self._performance_lock.release()

    def balance(self, on=False):
        with self._lock:
            self._queue("CMD_BALANCE", 1 if on else 0)

    def position(self, x=0, y=0, z=0):
        with self._lock:
            self._lifted_leg_positions.clear()
            self._queue("CMD_POSITION", int(x), int(y), int(z))

    def attitude(self, roll=0, pitch=0, yaw=0):
        with self._lock:
            self._lifted_leg_positions.clear()
            self._queue("CMD_ATTITUDE", int(roll), int(pitch), int(yaw))

    def head_vertical(self, angle=90):
        with self._lock:
            self.control.servo.set_servo_angle(0, max(60, min(int(angle), 180)))

    def head_horizontal(self, angle=90):
        with self._lock:
            self.control.servo.set_servo_angle(1, max(0, min(int(angle), 180)))

    def head_pose(self, pose="center"):
        poses = {
            "center": (90, 90),
            "forward": (90, 90),
            "left": (120, 90),
            "right": (60, 90),
            "up": (90, 120),
            "down": (90, 70),
        }
        pose = str(pose).lower()
        if pose not in poses:
            raise ValueError("pose must be center, forward, left, right, up, or down")
        horizontal, vertical = poses[pose]
        self.head_horizontal(horizontal)
        self.head_vertical(vertical)
        return {
            "accepted": True,
            "pose": pose,
            "horizontal": horizontal,
            "vertical": vertical,
        }

    def buzzer_on(self):
        self._peripheral("buzzer", "buzzer", "Buzzer").set_state(True)

    def buzzer_off(self):
        self._peripheral("buzzer", "buzzer", "Buzzer").set_state(False)

    def led_color(self, red=255, green=255, blue=255):
        values = [max(0, min(int(value), 255)) for value in (red, green, blue)]
        self._run_led_command(["CMD_LED", *(str(value) for value in values)])

    def led_mode(self, mode=0):
        self._run_led_command(["CMD_LED_MOD", str(int(mode))])

    def _run_led_command(self, command):
        if self._led_thread is not None and self._led_thread.is_alive():
            try:
                importlib.import_module("Thread").stop_thread(self._led_thread)
            except (ImportError, AttributeError):
                if command[1] != "0":
                    raise RuntimeError("The current LED animation cannot be replaced safely")
        led = self._peripheral("led", "led", "Led")
        self._led_thread = threading.Thread(
            target=led.process_light_command, args=(command,), daemon=True
        )
        self._led_thread.start()

    def _camera_frame(self, timeout=10.0):
        camera = self._peripheral("camera", "camera", "Camera")
        if not hasattr(camera, "streaming"):
            raise RuntimeError("No camera device is available")
        if not camera.streaming:
            camera.start_stream()
        wait_seconds = min(max(float(timeout), 0.1), 12.0)
        output = getattr(camera, "streaming_output", None)
        condition = getattr(output, "condition", None)
        if condition is not None:
            # Freenove's get_frame() waits forever. Waiting on its published
            # condition directly gives us a bounded wait without leaving a
            # blocked reader thread behind after a timeout.
            with condition:
                previous = output.frame
                fresh = condition.wait_for(
                    lambda: output.frame is not None and output.frame is not previous,
                    timeout=wait_seconds,
                )
                if not fresh:
                    raise TimeoutError("Camera did not produce a fresh frame")
                frame = output.frame
        else:
            # Small vendor-compatible fallback used by test doubles and older
            # camera wrappers that do not expose StreamingOutput.
            frames = queue.Queue(maxsize=1)

            def read_frame():
                try:
                    frames.put((camera.get_frame(), None))
                except Exception as exc:
                    frames.put((None, exc))

            threading.Thread(target=read_frame, daemon=True).start()
            try:
                frame, error = frames.get(timeout=wait_seconds)
            except queue.Empty as exc:
                raise TimeoutError("Camera did not produce a frame") from exc
            if error is not None:
                raise error
        if not frame:
            raise RuntimeError("Camera returned an empty frame")
        return frame

    def camera_capture(self, filename="image.jpg", timeout=10.0):
        frame = self._camera_frame(timeout)
        capture_dir = Path(os.environ.get("ACAMP_CAPTURE_DIR", "/tmp/acamp-robot-captures"))
        capture_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(str(filename)).name or "image.jpg"
        destination = (capture_dir / safe_name).resolve()
        destination.write_bytes(frame)
        return str(destination)

    def sonic(self):
        return self._peripheral("ultrasonic", "ultrasonic", "Ultrasonic").get_distance()

    def distance_read(self, samples=5, interval=0.05):
        """Return a robust summary of several forward ultrasonic readings."""
        samples = int(samples)
        if not 1 <= samples <= 20:
            raise ValueError("samples must be between 1 and 20")
        interval = float(interval)
        if not 0 <= interval <= 0.2:
            raise ValueError("interval must be between 0 and 0.2")
        readings = []
        for index in range(samples):
            value = self.sonic()
            if value is not None:
                readings.append(float(value))
            if interval and index + 1 < samples:
                self._sleep(interval)
        if not readings:
            raise RuntimeError("Ultrasonic sensor returned no valid readings")
        return {
            "unit": "cm",
            "median": round(statistics.median(readings), 2),
            "minimum": round(min(readings), 2),
            "maximum": round(max(readings), 2),
            "readings": readings,
            "samples_requested": samples,
            "samples_valid": len(readings),
        }

    def power(self):
        raw = self._peripheral("adc", "adc", "ADC").read_battery_voltage()
        if not isinstance(raw, (list, tuple)) or len(raw) < 2:
            raise RuntimeError(
                "Hexapod ADC returned an invalid voltage pair; expected servo and Raspberry Pi voltages"
            )
        voltages = [float(raw[0]), float(raw[1])]
        return {
            "servo_voltage_v": voltages[0],
            "raspberry_pi_voltage_v": voltages[1],
            "raw_voltages": voltages,
            "raw_order": ["servo_power", "raspberry_pi_power"],
        }

    def ball_start(self):
        self.head_vertical(90)
        self.head_horizontal(90)
        self._ball_active = True
        self._ball_tracking = True
        self._ball_stop.clear()
        self._reset_ball_pid()
        if self._ball_thread is None or not self._ball_thread.is_alive():
            self._ball_thread = threading.Thread(target=self._ball_tracking_loop, daemon=True)
            self._ball_thread.start()
        return {"accepted": True, "state": "ongoing"}

    def ball_stop(self):
        self._ball_active = False
        self._ball_tracking = False
        self._ball_stop.set()
        if (
            self._ball_thread is not None
            and self._ball_thread.is_alive()
            and threading.current_thread() is not self._ball_thread
        ):
            self._ball_thread.join(timeout=2.5)
        self.stop()
        return {"state": "not tracking"}

    def ball_state(self):
        if self._ball_active:
            return "ongoing" if self._ball_tracking else "completed"
        return "not tracking"

    def _ball_tracking_loop(self):
        cv2 = importlib.import_module("cv2")
        numpy = importlib.import_module("numpy")
        while not self._ball_stop.is_set():
            try:
                encoded = self._camera_frame(timeout=2.0)
                frame = cv2.imdecode(
                    numpy.frombuffer(encoded, dtype=numpy.uint8), cv2.IMREAD_COLOR
                )
                if frame is None:
                    raise RuntimeError("Camera returned an undecodable frame")
                detection = self._detect_red_ball(frame, cv2)
                step, angle = self._update_ball_observation(
                    detection, now=time.monotonic()
                )
                self.move(gait=1, x=0, y=step, angle=angle)
                self._ball_tracking = not (step == 0 and angle == 0)
            except Exception:
                self.stop()
                self._ball_active = False
                self._ball_tracking = False
                return

    @staticmethod
    def _detect_red_ball(frame, cv2):
        """Detect a ball exactly as the proven 01 tracker did."""
        filtered = cv2.GaussianBlur(frame, (3, 3), 0)
        filtered = cv2.cvtColor(filtered, cv2.COLOR_BGR2HSV)
        binary = cv2.inRange(filtered, (0, 180, 180), (5, 255, 255))
        binary = cv2.dilate(binary, None, iterations=1)
        contours = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )[-2]
        if not contours:
            return None
        contour = max(contours, key=cv2.contourArea)
        ((_circle_x, _circle_y), radius) = cv2.minEnclosingCircle(contour)
        moments = cv2.moments(contour)
        if radius < 7 or moments["m00"] <= 0:
            return None
        center_x = int(moments["m10"] / moments["m00"])
        return center_x, radius

    def _reset_ball_pid(self):
        self._pid_x = _TrackingPID(p=0.05, i=0.005, d=0.02)
        self._pid_distance = _TrackingPID(p=0.3, i=0.05, d=0.05)
        self._pid_x.set_point = 180
        self._pid_distance.set_point = 60
        self._ball_center_x = None
        self._ball_radius = None
        self._ball_missed_frames = 0
        self._ball_last_frame_at = None
        self._ball_frame_interval_ms = None
        self._ball_last_command = (0, 0)

    def _update_ball_observation(self, detection, now=None):
        """Smooth detections and tolerate brief losses without stop-start motion."""
        now = time.monotonic() if now is None else float(now)
        if self._ball_last_frame_at is not None:
            self._ball_frame_interval_ms = (now - self._ball_last_frame_at) * 1000
        self._ball_last_frame_at = now
        if detection is None:
            self._ball_missed_frames += 1
            if self._ball_missed_frames <= self._BALL_LOSS_GRACE_FRAMES:
                return self._ball_last_command
            self._ball_last_command = (0, 0)
            return self._ball_last_command

        center_x, radius = (float(value) for value in detection)
        alpha = self._BALL_SMOOTHING_ALPHA
        if self._ball_center_x is None:
            self._ball_center_x, self._ball_radius = center_x, radius
        else:
            self._ball_center_x += alpha * (center_x - self._ball_center_x)
            self._ball_radius += alpha * (radius - self._ball_radius)
        self._ball_missed_frames = 0
        self._ball_last_command = self._ball_motion(
            self._ball_center_x, self._ball_radius
        )
        return self._ball_last_command

    def _ball_motion(self, center_x, radius):
        """Return forward step and clockwise angle for a detected red ball."""
        if float(radius) <= 0:
            raise ValueError("radius must be positive")
        distance = round(2700 / (2 * float(radius)))
        if 170 <= float(center_x) <= 190:
            self._pid_x.last_error = 0
            self._pid_x.i_error = 0
            angle = 0
        else:
            angle = max(-10, min(10, int(self._pid_x.compute(float(center_x)))))
            if angle == 0:
                angle = -1 if center_x < 180 else 1
        if 55 <= distance <= 65:
            self._pid_distance.last_error = 0
            self._pid_distance.i_error = 0
            step = 0
        else:
            step = max(-15, min(15, int(self._pid_distance.compute(distance))))
            if step == 0:
                step = 1 if distance > 60 else -1
        return step, angle

    def _assert_leg_index(self, leg_index):
        if not 0 <= int(leg_index) <= 5:
            raise ValueError("leg_index must be between 0 and 5")

    def _ensure_manual_leg_allowed(self):
        if self._moving or self._ball_active:
            raise RuntimeError("Stop movement and ball tracking before manual leg control")

    @staticmethod
    def _human_leg_index(leg):
        leg = int(leg)
        if not 1 <= leg <= 6:
            raise ValueError("leg must be between 1 and 6")
        return leg - 1

    def _prepare_semantic_leg_control(self):
        if self._ball_active:
            self.ball_stop()
        if self._moving:
            self.stop()
            # Let Freenove's condition monitor consume the stop before a direct
            # leg update replaces its gait-generated joint angles.
            time.sleep(0.15)

    def lift_leg(self, leg, lift=30):
        """Lift one human-numbered leg relative to its current resting point."""
        leg_index = self._human_leg_index(leg)
        lift = int(lift)
        if not 5 <= lift <= 40:
            raise ValueError("lift must be between 5 and 40")
        self._prepare_semantic_leg_control()
        self._ensure_manual_leg_allowed()
        original = self._lifted_leg_positions.get(
            leg_index, list(self.control.leg_positions[leg_index])
        )
        newly_saved = leg_index not in self._lifted_leg_positions
        if newly_saved:
            self._lifted_leg_positions[leg_index] = list(original)
        try:
            self.set_leg_position(
                leg_index, original[0], original[1], original[2] + lift
            )
        except Exception:
            if newly_saved:
                self._lifted_leg_positions.pop(leg_index, None)
            raise
        return {"accepted": True, "leg": leg_index + 1, "lift": lift}

    def lower_leg(self, leg):
        """Return one lifted human-numbered leg to its saved position."""
        leg_index = self._human_leg_index(leg)
        self._prepare_semantic_leg_control()
        original = self._lifted_leg_positions.pop(leg_index, None)
        if original is None:
            return {"accepted": True, "leg": leg_index + 1, "lowered": False}
        try:
            self.set_leg_position(leg_index, *original)
        except Exception:
            self._lifted_leg_positions[leg_index] = original
            raise
        return {"accepted": True, "leg": leg_index + 1, "lowered": True}

    def lower_all_legs(self):
        """Return every semantically lifted leg to its saved position."""
        lowered = []
        for leg_index in sorted(tuple(self._lifted_leg_positions)):
            result = self.lower_leg(leg_index + 1)
            if result["lowered"]:
                lowered.append(leg_index + 1)
        return {"accepted": True, "lowered_legs": lowered}

    def leg_positions(self):
        """Return a defensive copy of all six current vendor-frame positions."""
        with self._lock:
            return [list(position) for position in self.control.leg_positions]

    def set_leg_position(self, leg_index, x, y, z):
        self._ensure_manual_leg_allowed()
        leg_index = int(leg_index)
        self._assert_leg_index(leg_index)
        previous = list(self.control.leg_positions[leg_index])
        self.control.leg_positions[leg_index] = [int(x), int(y), int(z)]
        if not self.control.check_point_validity():
            self.control.leg_positions[leg_index] = previous
            raise ValueError("Leg position is outside the valid range")
        self.control.set_leg_angles()

    def set_leg_positions(self, positions):
        self._ensure_manual_leg_allowed()
        if len(positions) != 6:
            raise ValueError("positions must contain six [x, y, z] entries")
        previous = [list(position) for position in self.control.leg_positions]
        for index, position in enumerate(positions):
            if len(position) != 3:
                self.control.leg_positions = previous
                raise ValueError("Each leg position must contain three values")
            self.control.leg_positions[index] = [int(value) for value in position]
        if not self.control.check_point_validity():
            self.control.leg_positions = previous
            raise ValueError("Leg positions are outside the valid range")
        self.control.set_leg_angles()

    def set_leg_servo_angles(self, leg_index, a, b, c):
        self._ensure_manual_leg_allowed()
        leg_index = int(leg_index)
        self._assert_leg_index(leg_index)
        for channel, angle in zip(self._LEG_CHANNELS[leg_index], (a, b, c)):
            self.control.servo.set_servo_angle(channel, max(0, min(int(angle), 180)))

    def set_leg_servo_angles_all(self, angles):
        if len(angles) != 6:
            raise ValueError("angles must contain six [a, b, c] entries")
        for index, values in enumerate(angles):
            if len(values) != 3:
                raise ValueError("Each leg angle entry must contain three values")
            self.set_leg_servo_angles(index, *values)

    def set_leg_joint_angles(self, leg_index, a, b, c):
        leg_index = int(leg_index)
        self._assert_leg_index(leg_index)
        calibration = self.control.calibration_angles[leg_index]
        if leg_index < 3:
            values = (a + calibration[0], 90 - (b + calibration[1]), c + calibration[2])
        else:
            values = (a + calibration[0], 90 + b + calibration[1], 180 - (c + calibration[2]))
        self.set_leg_servo_angles(leg_index, *values)

    def set_leg_joint_angles_all(self, angles):
        if len(angles) != 6:
            raise ValueError("angles must contain six [a, b, c] entries")
        for index, values in enumerate(angles):
            if len(values) != 3:
                raise ValueError("Each leg angle entry must contain three values")
            self.set_leg_joint_angles(index, *values)

    def status(self):
        result = {
            "bridge_ready": True,
            "hardware_initialized": self.hardware_initialized,
            "moving": self._moving,
            "servo_power": self._servo_power,
            "speed": self.move_speed,
            "last_command": self._last_command,
            "turn_by": self._turn_by_state,
            "ball_tracking": {
                "active": self._ball_active,
                "tracking": self._ball_tracking,
                "center_x": self._ball_center_x,
                "radius": self._ball_radius,
                "missed_frames": self._ball_missed_frames,
                "frame_interval_ms": self._ball_frame_interval_ms,
                "last_motion": {
                    "step": self._ball_last_command[0],
                    "angle": self._ball_last_command[1],
                },
            },
        }
        if self.hardware_initialized:
            result["control_thread_alive"] = self.control.condition_thread.is_alive()
        return result

    def capabilities(self):
        return sorted(
            name
            for name in (
                "attitude", "balance", "ball_start", "ball_state", "ball_stop",
                "body_height", "distance_read", "emergency_stop",
                "buzzer_off", "buzzer_on", "camera_capture", "connect", "disconnect",
                "head_horizontal", "head_pose", "head_vertical", "imu_read", "led_color",
                "led_mode", "leg_positions", "lift_leg", "lower_all_legs", "lower_leg",
                "position", "move", "perform", "power",
                "rest", "servopower", "set_leg_joint_angles",
                "set_leg_joint_angles_all", "set_leg_position", "set_leg_positions",
                "set_leg_servo_angles", "set_leg_servo_angles_all", "sonic", "speed",
                "stand", "stop", "tilt_read", "timed_move", "turn", "turn_by", "walk",
            )
        )


def load_control(server_dir: Path):
    server_dir = server_dir.resolve()
    if not server_dir.is_dir():
        raise FileNotFoundError(f"Freenove server directory not found: {server_dir}")
    sys.path.insert(0, str(server_dir))
    # Freenove's vendor code reads point.txt relative to the process cwd.
    os.chdir(server_dir)
    from control import Control  # type: ignore

    return Control()


def load_device(server_dir: Path):
    device = FreenoveDevice(server_dir=server_dir)
    device.attach_control(load_control(server_dir))
    device.connect()
    return device


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for raw in self.rfile:
            request = json.loads(raw)
            request_id = request.get("id")
            method = request.get("method")
            args = request.get("args", [])
            kwargs = request.get("kwargs", {})
            try:
                if method == "ping":
                    result = {"pong": True, "protocol_version": BRIDGE_PROTOCOL_VERSION}
                elif method == "shutdown":
                    if self.server.device.hardware_initialized:
                        self.server.device.servopower(False)
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    result = {"shutting_down": True}
                elif method == "status":
                    result = self.server.device.status()
                    result["socket"] = self.server.server_address
                elif method == "servopower" and not bool(
                    kwargs.get("on", args[0] if args else True)
                ):
                    if self.server.device.hardware_initialized:
                        self.server.device.servopower(False)
                    result = None
                else:
                    peripheral_methods = {
                        "buzzer_off", "buzzer_on", "camera_capture", "capabilities",
                        "distance_read", "led_color", "led_mode", "power", "rest", "sonic",
                    }
                    if not self.server.device.hardware_initialized and method not in peripheral_methods:
                        if method not in {"connect", "servopower", "stand"}:
                            raise RuntimeError(
                                "Hardware is not initialized. After checking the movement area, call stand or servopower true."
                            )
                        with self.server.device_lock:
                            if not self.server.device.hardware_initialized:
                                self.server.device.attach_control(load_control(self.server.server_dir))
                    target = getattr(self.server.device, method)
                    if method.startswith("_") or not callable(target):
                        raise AttributeError(method)
                    result = target(*args, **kwargs)
                response = {"id": request_id, "ok": True, "result": result}
            except Exception as exc:
                response = {"id": request_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
            try:
                self.wfile.write(json.dumps(response, default=repr).encode() + b"\n")
            except (BrokenPipeError, ConnectionResetError):
                # The client timing out must never terminate the bridge process.
                return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--server-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.path.exists(args.socket):
        os.unlink(args.socket)
    with socketserver.ThreadingUnixStreamServer(args.socket, Handler) as server:
        server.device = FreenoveDevice(server_dir=args.server_dir)
        server.device_lock = threading.Lock()
        server.server_dir = args.server_dir
        try:
            server.serve_forever()
        finally:
            if server.device.hardware_initialized:
                server.device.stop()
                server.device.servopower(False)


if __name__ == "__main__":
    main()
