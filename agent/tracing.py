from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import TraceEvent


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def log_event(
    trace_path: Path,
    *,
    event_type: str,
    run_id: str,
    iteration_index: int,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a structured event to the JSONL trace file."""
    _ensure_parent(trace_path)
    event = TraceEvent(
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        run_id=run_id,
        iteration_index=iteration_index,
        payload=payload or {},
    )
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(event.model_dump_json() + "\n")

