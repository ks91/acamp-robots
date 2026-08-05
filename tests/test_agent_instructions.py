from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_agents_requires_loading_camp_instructions():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "read `CAMP.md`" in agents
    assert "beginning of every session" in agents


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
