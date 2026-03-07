from __future__ import annotations

from pathlib import Path

from agent.reflection import reflect
from agent.schemas import TestResult


def _make_result(stdout: str = "", stderr: str = "") -> TestResult:
    return TestResult(
        success=False,
        exit_code=1,
        duration_ms=100,
        stdout=stdout,
        stderr=stderr,
        command="pytest -q",
        cwd="/tmp",
    )


def test_reflection_handles_assertion_add(tmp_path: Path) -> None:
    result = _make_result(stderr="E       AssertionError: assert add(1, 2) == 3")
    reflection = reflect(result, tmp_path)

    assert reflection.error_signature == "assertion_add_a_plus_b"
    assert "add()" in reflection.root_cause
    assert reflection.fix_plan.patches
    patch = reflection.fix_plan.patches[0]
    assert patch.relative_path == "app.py"
    assert patch.new_content is not None


def test_reflection_handles_assertion_square(tmp_path: Path) -> None:
    result = _make_result(stderr="E       AssertionError: assert square(3) == 9")
    reflection = reflect(result, tmp_path)

    assert reflection.error_signature == "assertion_square_x_times_x"
    assert "square()" in reflection.root_cause
    assert reflection.fix_plan.patches
    assert reflection.fix_plan.patches[0].relative_path == "math_utils.py"


def test_reflection_handles_typeerror_missing_arg(tmp_path: Path) -> None:
    stderr = "E   TypeError: greet() missing 1 required positional argument: 'name'"
    result = _make_result(stderr=stderr)
    reflection = reflect(result, tmp_path)

    assert reflection.error_signature.startswith("typeerror_missing_arg_greet_name")
    assert "greet()" in reflection.root_cause
    patch = reflection.fix_plan.patches[0]
    assert patch.relative_path == "greetings.py"


def test_reflection_handles_attributeerror_missing_attr(tmp_path: Path) -> None:
    stderr = "E   AttributeError: 'Calculator' object has no attribute 'multiply'"
    result = _make_result(stderr=stderr)
    reflection = reflect(result, tmp_path)

    assert reflection.error_signature == "attributeerror_calculator_missing_multiply"
    assert "Calculator" in reflection.root_cause
    patch = reflection.fix_plan.patches[0]
    assert patch.relative_path == "calculator.py"


def test_reflection_handles_nameerror_missing_name(tmp_path: Path) -> None:
    stderr = "E   NameError: name 'PI' is not defined"
    result = _make_result(stderr=stderr)
    reflection = reflect(result, tmp_path)

    assert reflection.error_signature == "nameerror_missing_PI_constant"
    assert "PI constant" in reflection.root_cause
    patch = reflection.fix_plan.patches[0]
    assert patch.relative_path == "geometry.py"


def test_reflection_handles_importerror_local_module(tmp_path: Path) -> None:
    stderr = "E   ModuleNotFoundError: No module named 'util'"
    result = _make_result(stderr=stderr)
    reflection = reflect(result, tmp_path)

    assert reflection.error_signature == "importerror_missing_util_module"
    assert "util module" in reflection.root_cause
    patch = reflection.fix_plan.patches[0]
    assert patch.relative_path == "util.py"


def test_reflection_fallback_when_no_heuristic(tmp_path: Path) -> None:
    stderr = "E   RuntimeError: something unexpected"
    result = _make_result(stderr=stderr)
    reflection = reflect(result, tmp_path)

    assert reflection.fix_plan.patches == []
    assert reflection.root_cause == "No deterministic fix found for this failure."
    assert reflection.normalized_error_text
    # Signature should be stable for identical messages.
    reflection2 = reflect(result, tmp_path)
    assert reflection2.error_signature == reflection.error_signature

