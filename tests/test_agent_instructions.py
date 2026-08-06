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


def test_agents_documents_both_hardware_control_paths():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "hardware/Arm_Lib.py" in agents
    assert "scripts/stop-camera-containers.sh" in agents
    assert "scripts/hexapod-rpc.sh start" in agents
    assert "Unix-socket RPC bridge" in agents


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
