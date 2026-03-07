from __future__ import annotations

import sqlite3
from pathlib import Path

from agent.config import settings
from agent.controller import run_task
from agent.schemas import Plan, TestResult, Patch


def test_run_task_succeeds_on_fixable_sample_project(tmp_path: Path) -> None:
    # Use the real fixable sample task to exercise the full loop including
    # reflection, patching, and pytest execution.
    project_root = settings.project_root
    task_path = project_root / "tasks" / "sample_task_fixable.json"
    assert task_path.exists()

    run_task(task_path)

    run_root = settings.runs_root / task_path.stem
    summary_path = run_root / "summary.md"
    db_path = run_root / "run.db"

    assert summary_path.exists()
    summary = summary_path.read_text(encoding="utf-8")
    assert "- Status: PASS" in summary

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # At least one successful iteration.
        cur.execute("SELECT COUNT(*) FROM iterations WHERE status = 'success'")
        (success_count,) = cur.fetchone() or (0,)
        assert success_count >= 1

        # At least one applied patch and one reflection recorded.
        cur.execute("SELECT COUNT(*) FROM patches")
        (patch_count,) = cur.fetchone() or (0,)
        assert patch_count >= 1

        cur.execute("SELECT COUNT(*) FROM reflections")
        (reflection_count,) = cur.fetchone() or (0,)
        assert reflection_count >= 1
    finally:
        conn.close()


def test_circuit_breaker_aborts_on_repeated_failure(monkeypatch, tmp_path: Path) -> None:
    # Create a tiny dummy repo and task.
    project_root = settings.project_root
    task_dir = tmp_path / "task"
    repo_dir = task_dir / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    task_path = task_dir / "circuit_task.json"
    task_path.write_text(
        (
            '{\n'
            '  "goal": "Trigger circuit breaker.",\n'
            '  "repo_path": "repo",\n'
            '  "test_command": "pytest -q",\n'
            '  "allowlist_paths": []\n'
            '}\n'
        ),
        encoding="utf-8",
    )

    # Stub run_tests to always fail with the same output.
    def _fake_run_tests(workspace_root: Path, test_command: str, timeout_seconds: int) -> TestResult:  # type: ignore[override]
        return TestResult(
            success=False,
            exit_code=1,
            duration_ms=10,
            stdout="failing tests",
            stderr="assert False",
            command="pytest -q",
            cwd=str(workspace_root),
        )

    # Stub reflect to always produce the same error_signature.
    def _fake_reflect(result: TestResult, workspace_root: Path):  # type: ignore[override]
        plan = Plan(description="no-op", patches=[Patch(relative_path="dummy.txt", new_content="x", unified_diff=None)])
        from agent.schemas import Reflection

        return Reflection(
            error_signature="repeat-error",
            root_cause="always fails",
            fix_plan=plan,
            normalized_error_text="assert False",
        )

    import agent.controller as controller_mod
    import agent.model as model_mod

    class _FakeProvider(model_mod.ModelProvider):  # type: ignore[misc]
        def generate_initial_plan(self, task):
            return Plan(description="initial", patches=[Patch(relative_path="dummy.txt", new_content="x", unified_diff=None)])

        def reflect_and_propose(self, task, test_result, history, workspace_root):
            return _fake_reflect(test_result, workspace_root)

    monkeypatch.setattr(controller_mod, "run_tests", _fake_run_tests)
    monkeypatch.setattr(model_mod, "get_model_provider", lambda: _FakeProvider())

    run_task(task_path)

    # The run should have been created under the global runs_root.
    run_root = settings.runs_root / task_path.stem
    summary_path = run_root / "summary.md"
    db_path = run_root / "run.db"

    assert summary_path.exists()
    summary = summary_path.read_text(encoding="utf-8")
    assert "- Status: aborted_repeated_failure" in summary

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM iterations WHERE status = 'aborted_repeated_failure'")
        (aborted_count,) = cur.fetchone() or (0,)
        assert aborted_count >= 1
    finally:
        conn.close()


def test_run_task_resumability_uses_existing_workspace(tmp_path: Path) -> None:
    # Create a tiny repo with a single passing test.
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.joinpath("test_ok.py").write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")

    task_path = tmp_path / "resume_task.json"
    task_path.write_text(
        '{ "goal": "resumable run", "repo_path": "repo", "test_command": "pytest -q", "allowlist_paths": [] }',
        encoding="utf-8",
    )

    # Point runs_root at a temporary directory so we can inspect it.
    from agent import config as config_mod
    orig_settings = config_mod.settings
    config_mod.settings = type(
        "S",
        (),
        {
            **orig_settings.__dict__,
            "project_root": tmp_path,
            "runs_dir_name": "runs",
            "runs_root": tmp_path / "runs",
            "default_max_iterations": orig_settings.default_max_iterations,
            "pytest_timeout_seconds": orig_settings.pytest_timeout_seconds,
            "default_test_command": orig_settings.default_test_command,
            "circuit_breaker_repeats": orig_settings.circuit_breaker_repeats,
        },
    )()

    try:
        # First run creates the workspace directory structure.
        run_task(task_path)

        run_root = config_mod.settings.runs_root / task_path.stem
        workspace_root = run_root / "workspace"
        workspace_root.mkdir(parents=True, exist_ok=True)
        marker = workspace_root / "marker.txt"
        marker.write_text("keep-me", encoding="utf-8")

        # Second run should treat this as a resume and not wipe the workspace.
        run_task(task_path)

        assert marker.exists()
        assert marker.read_text(encoding="utf-8") == "keep-me"
    finally:
        config_mod.settings = orig_settings


def test_unsafe_patches_stop_run(monkeypatch, tmp_path: Path) -> None:
    # Create a dummy repo and task; make safety always fail.
    repo_dir = tmp_path / "repo"
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.joinpath("test_ok.py").write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")

    task_path = tmp_path / "unsafe_task.json"
    task_path.write_text(
        '{ "goal": "unsafe patch", "repo_path": "repo", "test_command": "pytest -q", "allowlist_paths": [] }',
        encoding="utf-8",
    )

    import agent.controller as controller_mod
    import agent.safety as safety_mod

    monkeypatch.setattr(
        safety_mod,
        "patches_are_safe",
        lambda patches: False,  # always treat patches as unsafe
    )

    # Also stub the model provider to always propose a patch so the safety check runs.
    from agent import model as model_mod

    class _UnsafeProvider(model_mod.ModelProvider):  # type: ignore[misc]
        def generate_initial_plan(self, task):
            return Plan(description="unsafe", patches=[Patch(relative_path="x.py", new_content="x=1", unified_diff=None)])

        def reflect_and_propose(self, task, test_result, history, workspace_root):
            return model_mod.HeuristicModelProvider().reflect_and_propose(task, test_result, history, workspace_root)

    monkeypatch.setattr(model_mod, "get_model_provider", lambda: _UnsafeProvider())

    run_task(task_path)

    run_root = settings.runs_root / task_path.stem
    summary_path = run_root / "summary.md"
    assert summary_path.exists()
    summary = summary_path.read_text(encoding="utf-8")
    # The run should have failed early due to unsafe patches; tests may not even run.
    assert "unsafe" in summary.lower()

