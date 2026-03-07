from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Static configuration used by the agent."""

    project_root: Path = Path(__file__).resolve().parents[1]
    runs_dir_name: str = "runs"
    default_max_iterations: int = 8
    pytest_timeout_seconds: int = 60
    default_test_command: str = "pytest -q"
    circuit_breaker_repeats: int = 2

    @property
    def runs_root(self) -> Path:
        return self.project_root / self.runs_dir_name


settings = Settings()

