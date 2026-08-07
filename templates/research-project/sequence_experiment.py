"""Create a short semantic choreography without editing the robot bridge."""
from acamp_robots.sequence import run_hexapod_sequence


STEPS = [
    {"call": "body_height", "args": ["low"], "pause": 0.3},
    {"call": "head_horizontal", "args": [105], "pause": 0.3},
    {"call": "attitude", "args": [0, 4, 0], "pause": 0.3},
    {"call": "attitude", "args": [0, 0, 0]},
]


def run(robot):
    return run_hexapod_sequence(robot, STEPS)
