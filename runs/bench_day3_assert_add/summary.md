# Run summary for bench_day3_assert_add

- Goal: Fix add() so that add(1, 2) == 3.
- Status: FAIL
- Iterations completed: 1

## Latest test output

```
F                                                                        [100%]
================================== FAILURES ===================================
____________________________ test_add_returns_sum _____________________________

    def test_add_returns_sum() -> None:
>       assert add(1, 2) == 3
E       assert -1 == 3
E        +  where -1 = add(1, 2)

..\..\..\tasks\bench_day3\assert_add_project\tests\test_app.py:7: AssertionError
=========================== short test summary info ===========================
FAILED tests\test_app.py::test_add_returns_sum - assert -1 == 3
```
