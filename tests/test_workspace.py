from __future__ import annotations

from pathlib import Path

from agent.workspace import prepare_run_directories, task_id_from_path


def test_task_id_from_path_uses_stem(tmp_path: Path) -> None:
    task_file = tmp_path / "example_task.json"
    task_file.write_text("{}", encoding="utf-8")
    assert task_id_from_path(task_file) == "example_task"


def test_prepare_run_directories_creates_structure(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.json"
    task_file.write_text("{}", encoding="utf-8")

    run_paths = prepare_run_directories(task_file, runs_root=tmp_path / "runs")

    assert run_paths.run_root.exists()
    assert run_paths.workspace_root.exists()
    assert run_paths.db_path.parent == run_paths.run_root
    assert run_paths.trace_path.parent == run_paths.run_root
    assert run_paths.summary_path.parent == run_paths.run_root

