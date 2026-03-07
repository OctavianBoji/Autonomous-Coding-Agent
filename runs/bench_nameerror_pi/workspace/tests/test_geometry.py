from __future__ import annotations

from geometry import circle_area


def test_circle_area_uses_pi() -> None:
    assert round(circle_area(1.0), 5) == 3.14159

