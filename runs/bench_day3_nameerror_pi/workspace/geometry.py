from __future__ import annotations


def circle_area(r: float) -> float:
    # Intentional bug: PI is not defined.
    return PI * r * r  # type: ignore[name-defined]

