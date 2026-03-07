# Run summary for sample_task

- Goal: Fix the add() function so that the tests pass.
- Status: FAIL
- Iterations completed: 1

## Latest test output

```
F                                                                        [100%]
================================== FAILURES ===================================
__________________________ test_add_fails_for_sample __________________________

    def test_add_fails_for_sample():
>       assert add(1, 2) == 3
E       assert -1 == 3
E        +  where -1 = add(1, 2)

tests\test_app.py:5: AssertionError
=========================== short test summary info ===========================
FAILED tests\test_app.py::test_add_fails_for_sample - assert -1 == 3
1 failed in 0.09s
```
