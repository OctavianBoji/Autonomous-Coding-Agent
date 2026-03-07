from __future__ import annotations

from pathlib import Path
import json

from agent.config import settings
from agent.eval import run_evaluation


def test_run_evaluation_collects_results_for_tasks_dir(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    bench_dir = project_root / "tasks" / "bench"

    results = run_evaluation(bench_dir, max_iters=1)

    assert isinstance(results, list)
    assert len(results) >= 6
    for r in results:
        assert r.task_id
        assert isinstance(r.time_ms, int)
        assert isinstance(r.iterations, int)
        assert isinstance(r.final_status, str)

    # Metrics JSON should exist and contain a list of dicts.
    eval_files = sorted(settings.runs_root.glob("eval_*.json"))
    assert eval_files, "Expected at least one eval_*.json file"
    data = json.loads(eval_files[-1].read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert all("task_id" in item and "final_status" in item for item in data)

