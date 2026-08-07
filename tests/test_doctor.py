from pathlib import Path

from acamp_robots.doctor import Check, inspect_research_environment


def test_research_doctor_reports_project_and_vision_readiness(tmp_path, monkeypatch):
    (tmp_path / ".acamp-robot.json").write_text('{"robot":"hexapod","settings":{}}')
    (tmp_path / ".venv").mkdir()
    (tmp_path / "projects").mkdir()

    def available(name):
        return name in {"numpy", "cv2", "cv2.aruco"}

    checks = inspect_research_environment(tmp_path, module_available=available)
    by_name = {check.name: check for check in checks}
    assert by_name["robot configuration"].ok
    assert by_name["virtual environment"].ok
    assert by_name["local projects directory"].ok
    assert by_name["NumPy"].ok
    assert by_name["OpenCV marker backend"].ok


def test_check_exit_status_distinguishes_required_and_optional_failures():
    assert Check("optional", False, "missing", required=False).exit_failure is False
    assert Check("required", False, "missing", required=True).exit_failure is True


def test_strict_vision_makes_missing_marker_support_a_failure(tmp_path):
    (tmp_path / ".acamp-robot.json").write_text('{"robot":"hexapod"}')
    (tmp_path / ".venv").mkdir()
    (tmp_path / "projects").mkdir()
    checks = inspect_research_environment(
        tmp_path, module_available=lambda name: False, strict_vision=True
    )
    assert any(check.name == "OpenCV marker backend" and check.exit_failure for check in checks)
