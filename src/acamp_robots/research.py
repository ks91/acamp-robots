from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def create_project(
    name: str,
    *,
    root: Path | str | None = None,
    template_root: Path | str | None = None,
) -> Path:
    """Create one Git-ignored participant research project from the template."""
    if not PROJECT_NAME.fullmatch(str(name)):
        raise ValueError("project name must use lowercase letters, digits, and hyphens")
    root = Path(root or Path.cwd()).resolve()
    template_root = Path(template_root or root / "templates").resolve()
    source = template_root / "research-project"
    if not source.is_dir():
        raise FileNotFoundError(f"research project template not found: {source}")
    projects = root / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    destination = projects / name
    if destination.exists():
        raise FileExistsError(f"project already exists: {destination}")
    shutil.copytree(source, destination)
    for path in destination.rglob("*"):
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            path.write_text(content.replace("{{PROJECT_NAME}}", name), encoding="utf-8")
    return destination


class ExperimentLog:
    """Append anonymous, structured experiment trials as JSON Lines."""

    def __init__(self, path: Path | str, clock: Callable[[], str] | None = None):
        self.path = Path(path)
        self.clock = clock or self._utc_now

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def record(
        self,
        *,
        question: str,
        hypothesis: str = "",
        parameters: dict[str, Any] | None = None,
        observation: str = "",
        result: Any = None,
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        artifacts = list(artifacts or [])
        for artifact in artifacts:
            path = Path(artifact)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("artifact paths must be relative to the research project")
        record = {
            "recorded_at": self.clock(),
            "question": str(question),
            "hypothesis": str(hypothesis),
            "parameters": parameters or {},
            "observation": str(observation),
            "result": result,
            "artifacts": artifacts,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record
