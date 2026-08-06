from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .config import RobotConfig


class RobotController(Protocol):
    """Minimum runtime contract implemented by every robot plugin."""

    def status(self) -> Any: ...

    def call(self, method: str, *args: Any, **kwargs: Any) -> Any: ...

    def stop(self) -> Any: ...


class ControllerFactory(Protocol):
    def __call__(self, config: RobotConfig, root: Path) -> RobotController: ...
