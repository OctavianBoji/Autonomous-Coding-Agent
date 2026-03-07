from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import settings


@dataclass
class RunPaths:
    run_id: str
    run_root: Path
    workspace_root: Path
    db_path: Path
    trace_path: Path
    summary_path: Path


def task_id_from_path(task_path: Path) -> str:
    """Derive a task identifier from the task file name."""
    return task_path.stem


def prepare_run_directories(task_path: Path, *, runs_root: Path | None = None) -> RunPaths:
    """Create the run directory structure for a given task."""
    task_id = task_id_from_path(task_path)
    root = runs_root or settings.runs_root
    run_root = root / task_id
    workspace_root = run_root / "workspace"
    db_path = run_root / "run.db"
    trace_path = run_root / "trace.jsonl"
    summary_path = run_root / "summary.md"

    workspace_root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        run_id=task_id,
        run_root=run_root,
        workspace_root=workspace_root,
        db_path=db_path,
        trace_path=trace_path,
        summary_path=summary_path,
    )


def copy_repo_to_workspace(repo_path: Path, workspace_root: Path) -> None:
    """Copy the source repository into the workspace directory."""
    if workspace_root.exists():
        # Remove previous contents to ensure a clean workspace for this run.
        shutil.rmtree(workspace_root)
    workspace_root.mkdir(parents=True, exist_ok=True)

    # Copy the entire tree; this is safe as long as repo_path is inside the project root.
    shutil.copytree(repo_path, workspace_root, dirs_exist_ok=True)

