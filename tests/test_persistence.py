from __future__ import annotations

from pathlib import Path

from agent.persistence import (
    ensure_run_record,
    init_db,
    insert_iteration,
    insert_test_result,
)
from agent.schemas import TestResult


def test_persistence_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "run.db"
    init_db(db_path)

    ensure_run_record(db_path, run_id="run1", goal="goal", created_at="now")
    iteration_id = insert_iteration(
        db_path,
        run_id="run1",
        iteration_index=0,
        status="running",
        created_at="now",
    )

    result = TestResult(
        success=False,
        exit_code=1,
        duration_ms=100,
        stdout="out",
        stderr="err",
        command="pytest -q",
        cwd="/tmp",
    )
    insert_test_result(db_path, iteration_id=iteration_id, result=result)

