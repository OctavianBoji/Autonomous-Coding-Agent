from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import List

from .schemas import TestResult
from .config import settings


class ExecutionError(RuntimeError):
    pass


def _build_command(test_command: str) -> List[str]:
    """
    Build the subprocess command list for running tests.

    The agent always dispatches pytest via `python -m pytest -q` so that it
    does not depend on any PATH configuration and remains deterministic across
    environments. The `test_command` parameter is currently ignored but kept
    for interface compatibility.
    """
    return [sys.executable, "-m", "pytest", "-q"]


def run_tests(
    workspace_root: Path,
    test_command: str,
    timeout_seconds: int,
) -> TestResult:
    """Run tests inside the workspace using pytest (or a custom command)."""
    cmd = _build_command(test_command)
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=workspace_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
        )
        duration = time.perf_counter() - start
        duration_ms = int(duration * 1000)
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start
        duration_ms = int(duration * 1000)
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + "\nTESTS TIMED OUT"
        return TestResult(
            success=False,
            exit_code=-1,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            command=" ".join(cmd),
            cwd=str(workspace_root),
        )
    except OSError as exc:  # e.g. command not found
        duration = time.perf_counter() - start
        raise ExecutionError(f"Failed to execute tests: {exc}") from exc

    return TestResult(
        success=proc.returncode == 0,
        exit_code=proc.returncode,
        duration_ms=int(duration * 1000),
        stdout=proc.stdout,
        stderr=proc.stderr,
        command=" ".join(cmd),
        cwd=str(workspace_root),
    )

