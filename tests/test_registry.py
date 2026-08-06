import json
import importlib.util
from pathlib import Path

import pytest

from acamp_robots.config import RobotConfig
from acamp_robots.controller import create_controller
from acamp_robots.registry import load_robot_specs, validate_robot_specs


ROOT = Path(__file__).parents[1]


def mock_registry():
    return {
        "mock": {
            "display_name": "Mock Robot",
            "controller_factory": "mock_robot:build",
            "instructions": ".agents/robots/mock.md",
            "prepare_command": ["scripts/mock-prepare.sh"],
            "system_site_packages": False,
            "default_settings": {"port": 7},
            "setup_note": "Mock ready.",
        }
    }


def test_registry_accepts_a_third_robot_without_core_conditionals(tmp_path, monkeypatch):
    module = tmp_path / "mock_robot.py"
    module.write_text(
        "class Controller:\n"
        "    def __init__(self, config, root): self.robot = config.robot; self.root = str(root); self.port = config.get('port')\n"
        "    def status(self): return {'robot': self.robot}\n"
        "    def call(self, method, *args, **kwargs): return [method, args, kwargs]\n"
        "    def stop(self): return None\n"
        "def build(config, root): return Controller(config, root)\n"
    )
    monkeypatch.syspath_prepend(tmp_path)
    (tmp_path / "robots.json").write_text(json.dumps(mock_registry()))
    specs = load_robot_specs(tmp_path)
    assert specs["mock"].default_settings == {"port": 7}
    controller = create_controller(RobotConfig("mock", {"port": 9}), tmp_path)
    assert (controller.robot, controller.root, controller.port) == ("mock", str(tmp_path), 9)


def test_third_robot_configure_and_prepare_flow_needs_no_new_branch(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    instructions = tmp_path / ".agents" / "robots"
    scripts.mkdir(parents=True)
    instructions.mkdir(parents=True)
    (tmp_path / "robots.json").write_text(json.dumps(mock_registry()))
    (tmp_path / "mock_robot.py").write_text("def build(config, root): return object()\n")
    monkeypatch.syspath_prepend(tmp_path)
    (instructions / "mock.md").write_text("# Mock\n")
    prepare = scripts / "mock-prepare.sh"
    prepare.write_text("#!/bin/sh\nprintf prepared > \"$PWD/prepared\"\n")
    prepare.chmod(0o755)

    spec = importlib.util.spec_from_file_location(
        "robot_admin_test", ROOT / "scripts" / "robot-admin.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)

    assert module.main(["configure", "--robot", "mock", "--set", "port=9"]) == 0
    stored = json.loads((tmp_path / ".acamp-robot.json").read_text())
    assert stored == {"robot": "mock", "settings": {"port": 9}}
    assert module.main(["prepare"]) == 0
    assert (tmp_path / "prepared").read_text() == "prepared"


def test_registry_paths_and_factories_resolve_for_every_supported_robot():
    for spec in validate_robot_specs(ROOT).values():
        assert (ROOT / spec.instructions).is_file()
        assert (ROOT / spec.prepare_command[0]).is_file()
        assert callable(spec.load_controller_factory())


def test_controller_contract_is_enforced_for_plugins(tmp_path, monkeypatch):
    (tmp_path / "bad_robot.py").write_text("def build(config, root): return object()\n")
    registry = mock_registry()
    registry["mock"]["controller_factory"] = "bad_robot:build"
    (tmp_path / "robots.json").write_text(json.dumps(registry))
    monkeypatch.syspath_prepend(tmp_path)
    with pytest.raises(TypeError, match="status, call, stop"):
        create_controller(RobotConfig("mock"), tmp_path)
