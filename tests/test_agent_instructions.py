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
