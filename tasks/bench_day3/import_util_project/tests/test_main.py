from __future__ import annotations

from main import compute_total


def test_compute_total_uses_util_add() -> None:
    assert compute_total(2, 5) == 7

