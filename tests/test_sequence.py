import pytest

from acamp_robots.sequence import SequenceValidationError, run_hexapod_sequence, validate_hexapod_sequence


class FakeRobot:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def call(self, method, *args):
        self.calls.append((method, args))
        if method == self.fail_on:
            raise RuntimeError("test failure")

    def stop(self):
        self.calls.append(("stop", ()))


def test_sequence_runs_bounded_semantic_steps_and_always_stops():
    robot = FakeRobot()
    sleeps = []
    steps = [
        {"call": "body_height", "args": ["low"], "pause": 0.2},
        {"call": "turn", "args": ["clockwise", 0.3, 5], "pause": 0.1},
        {"call": "head_horizontal", "args": [105]},
    ]
    result = run_hexapod_sequence(robot, steps, sleep=sleeps.append)
    assert result["steps_completed"] == 3
    assert robot.calls[-1] == ("stop", ())
    assert sleeps == [0.2, 0.1]


def test_sequence_stops_after_a_step_failure():
    robot = FakeRobot(fail_on="attitude")
    with pytest.raises(RuntimeError, match="test failure"):
        run_hexapod_sequence(robot, [{"call": "attitude", "args": [2, 0, 0]}])
    assert robot.calls[-1] == ("stop", ())


@pytest.mark.parametrize(
    "steps",
    [
        [{"call": "move", "args": [1, 0, 30, 0]}],
        [{"call": "set_leg_servo_angles", "args": [0, 90, 90, 90]}],
        [{"call": "turn", "args": ["clockwise", 6]}],
        [{"call": "position", "args": [0, 0, 0], "pause": 1.1}],
        [{"call": "position", "args": [0, 0, 0]}] * 41,
    ],
)
def test_sequence_rejects_unbounded_low_level_or_oversized_plans(steps):
    with pytest.raises(SequenceValidationError):
        validate_hexapod_sequence(steps)
