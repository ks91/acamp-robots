from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_agents_requires_loading_camp_instructions():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "read `CAMP.md`" in agents
    assert "beginning of every session" in agents


def test_agents_distinguishes_development_from_physical_operation():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "unconfigured development environment" in agents
    assert "active physical-robot session" in agents
    assert "Do not move a physical robot" in agents


def test_prepared_sessions_do_not_ask_children_for_safety_confirmation():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    camp = (ROOT / "CAMP.md").read_text(encoding="utf-8")
    assert "ACAMP_PHYSICAL_ROBOT_READY=1" in agents
    assert "without asking for confirmation" in agents
    assert 'Do not ask questions such as "Is the area safe?"' in agents
    assert "staff complete the physical safety check" in camp.lower()
    assert "do not ask participants for repeated safety confirmation" in camp.lower()


def test_agents_documents_both_hardware_control_paths():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "hardware/Arm_Lib.py" in agents
    assert "scripts/stop-camera-containers.sh" in agents
    assert "scripts/hexapod-rpc.sh start" in agents
    assert "Unix-socket RPC bridge" in agents
    assert "`hardware_initialized: false` is the normal safe state" in agents
    assert ".venv/bin/acamp-robot call stand" in agents
    assert "Use the direction-name API" in agents
    assert "positive `y` for forward" in agents
    assert "positive `x` for right" in agents
    assert "Never infer or guess vendor coordinates" in agents


def test_agents_uses_a_real_camera_frame_for_visual_questions():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert ".venv/bin/acamp-robot call camera_capture view.jpg" in agents
    assert "inspect that actual image" in agents
    assert "Never infer visual content from robot status" in agents
    assert "available while `hardware_initialized` is false" in agents


def test_agents_translates_rest_requests_to_servo_power_off():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "`休め`" in agents
    assert ".venv/bin/acamp-robot call rest" in agents
    assert "`止まれ`" in agents
    assert "retains servo power" in agents
    assert "disables servo power" in agents


def test_agents_documents_arm_body_and_natural_language_controls():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert ".venv/bin/acamp-robot call home" in agents
    assert "base rotation, lower link, middle link" in agents
    assert "wrist rotation accepts 0–270 degrees" in agents
    assert "`grip_object WIDTH_CM`" in agents
    assert "On DOFBOT, both an emergency stop and `rest` disable servo torque" in agents
    assert "`[90, 90, 90, 90, 90, 180]`" in agents
    assert "gripper is closed" in agents
    assert "`camera_forward` is `[90, 60, 60, 60, 90, 120]`" in agents
    assert "joint 2–4 totaling 180 degrees" in agents
    assert "`camera_work_area` is `[90, 120, 0, 0, 90, 30]`" in agents
    assert "Joint 1 determines horizontal direction" in agents
    assert ".venv/bin/acamp-robot call pose_info POSE_NAME" in agents


def test_agents_keeps_robot_skills_and_sensitive_files_scoped():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "under `skills/`" in agents
    assert "Do not install robot behaviors into `~/.codex/skills`" in agents
    assert "never commit logs" in agents
    assert "does not grant permission" in agents


def test_camp_template_contains_operational_sections():
    camp = (ROOT / "CAMP.md").read_text(encoding="utf-8")
    for heading in (
        "## Current camp",
        "## Language and communication",
        "## Program-specific role",
        "## Robot behavior",
        "## Safety and safeguarding",
        "## Operational notes",
    ):
        assert heading in camp
