# Run summary for bench_day3_nameerror_pi

- Goal: Fix NameError by defining PI constant used by circle_area.
- Status: FAIL
- Iterations completed: 1

## Latest test output

```
F                                                                        [100%]
================================== FAILURES ===================================
__________________________ test_circle_area_uses_pi ___________________________

    def test_circle_area_uses_pi() -> None:
>       assert round(circle_area(1.0), 5) == 3.14159
                     ^^^^^^^^^^^^^^^^

..\..\..\tasks\bench_day3\nameerror_pi_project\tests\test_geometry.py:7: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

r = 1.0

    def circle_area(r: float) -> float:
        # Intentional bug: PI is not defined.
>       return PI * r * r  # type: ignore[name-defined]
               ^^
E       NameError: name 'PI' is not defined

geometry.py:6: NameError
=========================== short test summary info ===========================
FAILED tests\test_geometry.py::test_circle_area_uses_pi - NameError: name 'PI...
```
