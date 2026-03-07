from __future__ import annotations


def compute_total(a: int, b: int) -> int:
    # Tests import util.add; util module is intentionally missing.
    from util import add  # type: ignore[import]

    return add(a, b)

