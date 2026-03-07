from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TaskConfig(BaseModel):
    """Configuration loaded from a task JSON file."""

    goal: str
    repo_path: str
    test_command: str = "pytest -q"
    allowlist_paths: Optional[List[str]] = None

    def resolved_repo_path(self, task_file: Path) -> Path:
        base = task_file.parent
        return (base / self.repo_path).resolve()


class Patch(BaseModel):
    """
    Representation of a single file edit.

    Exactly one of `new_content` or `unified_diff` must be provided.
    The `relative_path` is always interpreted relative to the workspace root.
    """

    relative_path: str
    new_content: str | None = None
    unified_diff: str | None = None

    @model_validator(mode="after")
    def _ensure_exactly_one_payload(self) -> "Patch":
        has_new = self.new_content is not None
        has_diff = self.unified_diff is not None
        if has_new == has_diff:
            # Either both set or neither set.
            raise ValueError("Exactly one of new_content or unified_diff must be provided.")
        return self


class Plan(BaseModel):
    """Minimal plan produced for an iteration."""

    description: str
    patches: List[Patch] = Field(default_factory=list)


class TestResult(BaseModel):
    """Normalized result of running the project's tests."""

    success: bool
    exit_code: int
    duration_ms: int
    stdout: str
    stderr: str
    command: str
    cwd: str
    __test__ = False


class TraceEvent(BaseModel):
    """Single JSONL trace event."""

    timestamp: datetime
    event_type: str
    run_id: str
    iteration_index: int
    payload: dict[str, Any]


class Reflection(BaseModel):
    """
    Structured reflection over a failing test run.

    error_signature is a stable identifier used for circuit breaking.
    fix_plan is a concrete, file-level edit plan for the next iteration.
    """

    error_signature: str
    root_cause: str
    fix_plan: Plan
    normalized_error_text: str

