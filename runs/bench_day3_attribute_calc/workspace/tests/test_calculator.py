from __future__ import annotations

from calculator import Calculator


def test_calculator_has_multiply() -> None:
    calc = Calculator()
    assert calc.multiply(2, 3) == 6

