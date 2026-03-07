from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable, List

from .config import settings
from .controller import run_task


@dataclass(frozen=True)
class EvalResult:
    task_id: str
    passed: bool
    iterations: int
    time_ms: int
    final_status: str


def _parse_summary(summary_path: Path) -> tuple[str, int]:
    """
    Parse summary.md written by the controller to extract final status and
    iterations completed.
    """
    status = "UNKNOWN"
    iterations = 0
    text = summary_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("- Status:"):
            status = line.split(":", 1)[1].strip()
        elif line.startswith("- Iterations completed:"):
            value = line.split(":", 1)[1].strip()
            try:
                iterations = int(value)
            except ValueError:
                iterations = 0
    return status, iterations


def _format_table(results: Iterable[EvalResult]) -> str:
    lines: List[str] = []
    header = "task_id\tPASS/FAIL\titerations\ttime_ms\tfinal_status"
    lines.append(header)
    for r in results:
        lines.append(
            f"{r.task_id}\t{'PASS' if r.passed else 'FAIL'}\t{r.iterations}\t{r.time_ms}\t{r.final_status}"
        )
    return "\n".join(lines)


def run_evaluation(tasks_dir: Path, max_iters: int | None = None) -> list[EvalResult]:
    """
    Run the agent on all task JSON files in `tasks_dir` and collect metrics.
    """
    task_paths = sorted(tasks_dir.glob("*.json"))
    results: list[EvalResult] = []

    for task_path in task_paths:
        task_id = task_path.stem
        start = perf_counter()
        run_task(task_path, max_iterations=max_iters)
        elapsed_ms = int((perf_counter() - start) * 1000)

        run_root = settings.runs_root / task_id
        summary_path = run_root / "summary.md"
        if not summary_path.exists():
            # If something went very wrong, record as failure with zero iterations.
            results.append(
                EvalResult(
                    task_id=task_id,
                    passed=False,
                    iterations=0,
                    time_ms=elapsed_ms,
                    final_status="MISSING_SUMMARY",
                )
            )
            continue

        final_status, iterations = _parse_summary(summary_path)
        passed = final_status == "PASS"
        results.append(
            EvalResult(
                task_id=task_id,
                passed=passed,
                iterations=iterations,
                time_ms=elapsed_ms,
                final_status=final_status,
            )
        )

    # Print a simple summary table.
    print(_format_table(results))

    # Persist metrics as JSON for offline analysis.
    settings.runs_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = settings.runs_root / f"eval_{timestamp}.json"
    data = [
        {
            "task_id": r.task_id,
            "passed": r.passed,
            "iterations": r.iterations,
            "time_ms": r.time_ms,
            "final_status": r.final_status,
        }
        for r in results
    ]
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return results

