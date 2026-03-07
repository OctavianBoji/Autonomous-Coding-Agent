from __future__ import annotations

from pathlib import Path

from agent.executor import run_tests


def test_run_tests_on_tiny_project(tmp_path: Path) -> None:
    # Create a tiny project with a single passing test.
    pkg = tmp_path / "proj"
    pkg.mkdir()
    tests_dir = pkg / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_one():\n    assert 1 == 1\n", encoding="utf-8")

    result = run_tests(
        workspace_root=pkg,
        test_command="pytest -q",
        timeout_seconds=30,
    )
    assert result.success
    assert result.exit_code == 0
    assert result.duration_ms >= 0
    assert "pytest" in result.command
    assert str(pkg) == result.cwd


def test_run_tests_times_out(tmp_path: Path) -> None:
    # Create a tiny project with a deliberately slow test to trigger timeout handling.
    pkg = tmp_path / "proj"
    pkg.mkdir()
    tests_dir = pkg / "tests"
    tests_dir.mkdir()
    tests_dir.joinpath("test_sleep.py").write_text(
        "import time\n\ndef test_sleep():\n    time.sleep(1)\n",
        encoding="utf-8",
    )

    result = run_tests(
        workspace_root=pkg,
        test_command="pytest -q",
        timeout_seconds=0,  # effectively immediate timeout
    )

    assert not result.success
    assert result.exit_code == -1
    assert "TESTS TIMED OUT" in result.stderr
    assert result.duration_ms >= 0

