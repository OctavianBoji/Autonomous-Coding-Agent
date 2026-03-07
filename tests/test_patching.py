from __future__ import annotations

import sqlite3
from pathlib import Path
import sqlite3
import difflib

from agent.patching import apply_patches
from agent.persistence import init_db
from agent.schemas import Patch
from agent.workspace import RunPaths


def _make_run_paths(root: Path) -> RunPaths:
    run_root = root / "run"
    workspace_root = run_root / "workspace"
    db_path = run_root / "run.db"
    trace_path = run_root / "trace.jsonl"
    summary_path = run_root / "summary.md"
    workspace_root.mkdir(parents=True, exist_ok=True)
    return RunPaths(
        run_id="run1",
        run_root=run_root,
        workspace_root=workspace_root,
        db_path=db_path,
        trace_path=trace_path,
        summary_path=summary_path,
    )


def test_apply_patches_writes_inside_workspace_and_persists(tmp_path: Path) -> None:
    run_paths = _make_run_paths(tmp_path)
    init_db(run_paths.db_path)

    patch = Patch(relative_path="file.txt", new_content="hello", unified_diff=None)

    apply_patches(run_paths, iteration_id=1, patches=[patch])

    target = run_paths.workspace_root / "file.txt"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello"

    # Verify persistence in the patches table.
    conn = sqlite3.connect(run_paths.db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT relative_path, new_content, unified_diff, diff_text, before_sha256, after_sha256 FROM patches"
        )
        row = cur.fetchone()
        assert row is not None
        relative_path, new_content, unified_diff, diff_text, before_sha, after_sha = row
        assert relative_path == "file.txt"
        assert new_content == "hello"
        assert unified_diff is None
        assert diff_text
        assert before_sha
        assert after_sha
    finally:
        conn.close()


def test_apply_patches_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    run_paths = _make_run_paths(tmp_path)
    init_db(run_paths.db_path)

    # Relative path that would escape the workspace.
    patch = Patch(relative_path="../outside.txt", new_content="x", unified_diff=None)

    try:
        apply_patches(run_paths, iteration_id=1, patches=[patch])
        assert False, "Expected ValueError for patch escaping workspace"
    except ValueError:
        pass


def test_apply_patches_supports_unified_diff(tmp_path: Path) -> None:
    run_paths = _make_run_paths(tmp_path)
    init_db(run_paths.db_path)

    target = run_paths.workspace_root / "code.py"
    original = "def add(a, b):\n    return a - b\n"
    target.write_text(original, encoding="utf-8")

    updated = "def add(a, b):\n    return a + b\n"
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=False),
            updated.splitlines(keepends=False),
            fromfile="code.py",
            tofile="code.py",
        )
    )
    diff_text = "\n".join(diff_lines) + "\n"

    patch = Patch(relative_path="code.py", new_content=None, unified_diff=diff_text)

    apply_patches(run_paths, iteration_id=1, patches=[patch])

    # File content should reflect the diff.
    assert target.read_text(encoding="utf-8") == updated

    # And the diff should be persisted.
    conn = sqlite3.connect(run_paths.db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT relative_path, new_content, unified_diff, diff_text, before_sha256, after_sha256 FROM patches"
        )
        row = cur.fetchone()
        assert row is not None
        relative_path, new_content, unified_diff, diff_text, before_sha, after_sha = row
        assert relative_path == "code.py"
        assert new_content is None
        assert "return a + b" in (unified_diff or "")
        assert diff_text
        assert before_sha
        assert after_sha
    finally:
        conn.close()

