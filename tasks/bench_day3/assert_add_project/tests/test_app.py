from __future__ import annotations

from app import add


def test_add_returns_sum() -> None:
    assert add(1, 2) == 3

