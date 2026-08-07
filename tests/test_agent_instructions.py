from pathlib import Path

from acamp_robots.registry import load_robot_specs


ROOT = Path(__file__).parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_root_agents_is_a_small_strict_instruction_router():
    agents = read("AGENTS.md")
    assert "beginning of every session" in agents
    assert "Read `CAMP.md`" in agents
    assert "Read `.agents/common.md`" in agents
    assert "read `robots.json`" in agents
    assert "entry whose key exactly matches" in agents
    assert "Do not read or apply another robot's module" in agents
    assert "unconfigured development environment" in agents
    assert "Yahboom" not in agents
    assert "Freenove" not in agents
    assert len(agents.splitlines()) < 50


def test_every_registered_robot_has_exactly_one_instruction_module():
    specs = load_robot_specs(ROOT)
    assert {"arm", "hexapod"} <= specs.keys()
    instruction_paths = [spec.instructions for spec in specs.values()]
    assert len(instruction_paths) == len(set(instruction_paths))
    for name, spec in specs.items():
        path = ROOT / spec.instructions
        assert path.is_file(), f"missing instructions for {name}: {path}"
        assert f"selects `{name}`" in path.read_text(encoding="utf-8")


def test_common_instructions_are_robot_independent():
    common = read(".agents/common.md")
    assert "ACAMP_PHYSICAL_ROBOT_READY=1" in common
    assert "without asking for confirmation" in common
    assert "under `skills/`" in common
    assert "Never commit logs" in common
    assert "Yahboom" not in common
    assert "Freenove" not in common
    assert "Arm_Lib.py" not in common
    assert "Unix-socket" not in common


def test_arm_module_contains_body_camera_and_language_semantics():
    arm = read(".agents/robots/arm.md")
    assert "hardware/Arm_Lib.py" in arm
    assert "scripts/stop-camera-containers.sh" in arm
    assert ".venv/bin/acamp-robot call home" in arm
    assert "base rotation, lower link, middle link" in arm
    assert "Joint 5 accepts 0–270 degrees" in arm
    assert "`[90, 90, 90, 90, 90, 180]`" in arm
    assert "`camera_forward` is `[90, 60, 60, 60, 90, 120]`" in arm
    assert "`camera_work_area` is `[90, 120, 0, 0, 90, 30]`" in arm
    assert ".venv/bin/acamp-robot call pose_info POSE_NAME" in arm


def test_hexapod_module_contains_rpc_direction_and_rest_semantics():
    hexapod = read(".agents/robots/hexapod.md")
    assert "Unix-socket RPC bridge" in hexapod
    assert "scripts/hexapod-rpc.sh start" in hexapod
    assert "`hardware_initialized: false`" in hexapod
    assert ".venv/bin/acamp-robot call stand" in hexapod
    assert ".venv/bin/acamp-robot call walk DIRECTION DURATION" in hexapod
    assert "positive `y` for forward" in hexapod
    assert "positive `x` for right" in hexapod
    assert ".venv/bin/acamp-robot call rest" in hexapod
    assert ".venv/bin/acamp-robot call turn DIRECTION DURATION" in hexapod
    assert "clockwise" in hexapod and "counterclockwise" in hexapod
    assert ".venv/bin/acamp-robot call body_height LEVEL" in hexapod
    assert "low`, `normal`, and `high" in hexapod
    assert "ball_start" in hexapod and "ball_stop" in hexapod
    assert ".venv/bin/acamp-robot call perform rock_and_roll" in hexapod
    assert "Do not refuse an imaginative request merely because it is imaginative" in hexapod


def test_camp_template_contains_operational_sections():
    camp = read("CAMP.md")
    for heading in (
        "## Current camp", "## Language and communication", "## Program-specific role",
        "## Robot behavior", "## Safety and safeguarding", "## Operational notes",
    ):
        assert heading in camp


def test_2026_summer_camp_instructions_capture_the_public_operating_context():
    camp = read("CAMP.md")
    assert "August 9–11, 2026" in camp
    assert "17 members" in camp
    assert "five color teams" in camp
    assert "Research is really play" in camp
    assert "Day 1:" in camp and "Day 2:" in camp and "Day 3:" in camp
    assert "GAMER PAT and LaTeX" in camp
    assert "approximately 12 robots with up to 2 additional units" in camp
    assert "50 continuous minutes" in camp
    assert "10 minutes of break per hour" in camp


def test_public_camp_instructions_exclude_private_manual_data():
    camp = read("CAMP.md")
    assert "deliberately excludes participant and staff names" in camp
    assert "the venue, accommodation" in camp
    assert "never request or expose private Discord details" in camp
    assert "Do not reveal network credentials" in camp
    assert "do not upload, publish, or externally message any media" in camp.lower()
    assert "room assignments" in camp
    assert "Treat the venue, accommodation, meeting points, routes" in camp
    assert "Never reveal, confirm, infer, geolocate" in camp
