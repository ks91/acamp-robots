from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any


class SequenceValidationError(ValueError):
    pass


_ALLOWED_HEXAPOD_CALLS = {
    "attitude",
    "body_height",
    "buzzer_off",
    "buzzer_on",
    "head_horizontal",
    "head_vertical",
    "led_color",
    "lift_leg",
    "lower_all_legs",
    "lower_leg",
    "perform",
    "position",
    "stop",
    "turn",
    "turn_by",
    "walk",
}


def validate_hexapod_sequence(
    steps: Sequence[dict[str, Any]], *, max_steps: int = 40, max_seconds: float = 60.0
) -> list[dict[str, Any]]:
    """Validate a short semantic choreography without allowing raw motion calls."""
    if not isinstance(steps, (list, tuple)) or not 1 <= len(steps) <= max_steps:
        raise SequenceValidationError(f"sequence must contain 1 to {max_steps} steps")
    normalized = []
    estimated_seconds = 0.0
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise SequenceValidationError(f"step {index} must be an object")
        method = str(step.get("call", ""))
        if method not in _ALLOWED_HEXAPOD_CALLS:
            raise SequenceValidationError(f"step {index} uses unsupported call: {method}")
        args = step.get("args", [])
        if not isinstance(args, list):
            raise SequenceValidationError(f"step {index} args must be a list")
        pause = float(step.get("pause", 0.0))
        if not 0 <= pause <= 1.0:
            raise SequenceValidationError(f"step {index} pause must be between 0 and 1")
        if method in {"walk", "turn"}:
            duration = float(args[1]) if len(args) >= 2 else 1.0
            if not 0 < duration <= 30:
                raise SequenceValidationError(f"step {index} duration must be at most 30")
            estimated_seconds += duration
        elif method == "turn_by":
            degrees = float(args[1]) if len(args) >= 2 else 90.0
            max_seconds_arg = (
                float(args[4])
                if len(args) >= 5
                else max(5.0, min(30.0, degrees / 15.0))
            )
            if not 0 < max_seconds_arg <= 30:
                raise SequenceValidationError(
                    f"step {index} turn_by max_seconds must be at most 30"
                )
            estimated_seconds += max_seconds_arg
        elif method == "perform":
            estimated_seconds += 1.5
        estimated_seconds += pause
        normalized.append({"call": method, "args": list(args), "pause": pause})
    if estimated_seconds > max_seconds:
        raise SequenceValidationError(
            f"estimated sequence duration exceeds {max_seconds:g} seconds"
        )
    return normalized


def run_hexapod_sequence(
    robot,
    steps: Sequence[dict[str, Any]],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run a validated sequence and issue stop even after interruption or failure."""
    normalized = validate_hexapod_sequence(steps)
    completed = 0
    try:
        for step in normalized:
            robot.call(step["call"], *step["args"])
            completed += 1
            if step["pause"]:
                sleep(step["pause"])
    finally:
        robot.stop()
    return {"accepted": True, "steps_completed": completed}
