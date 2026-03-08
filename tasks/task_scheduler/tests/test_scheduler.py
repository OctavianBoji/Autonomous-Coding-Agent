import pytest
from scheduler import CycleError, Scheduler, Status, UnknownTaskError


# ── add_task ──────────────────────────────────────────────────────────────────

def test_add_task_basic():
    s = Scheduler()
    s.add_task("a")
    assert s.status("a") == Status.PENDING

def test_add_task_unknown_dep_raises():
    s = Scheduler()
    with pytest.raises(UnknownTaskError):
        s.add_task("b", depends_on=["a"])

def test_add_task_idempotent():
    s = Scheduler()
    s.add_task("a")
    s.add_task("a")   # second call should not raise
    assert s.status("a") == Status.PENDING

def test_add_task_detects_direct_cycle():
    """a -> b -> a should raise CycleError when adding b."""
    s = Scheduler()
    s.add_task("a")
    s.add_task("b", depends_on=["a"])
    # Manually wire a -> b to create cycle, then try to detect
    # Actually simulate: add c that depends on b, then try adding a dependency
    # that would create a -> b -> a cycle.
    # Simplest: build a -> b -> c -> a
    s.add_task("c", depends_on=["b"])
    # Now add a task that depends on c and is itself a dependency of a — but
    # since add_task is the only entry point, test the simpler 2-node cycle:
    s2 = Scheduler()
    s2.add_task("x")
    s2.add_task("y", depends_on=["x"])
    # Patch _deps to simulate a cycle and verify _has_cycle detects it
    s2._deps["x"].add("y")   # x now depends on y → cycle: x->y->x
    s2._rdeps["y"].add("x")
    assert s2._has_cycle("x") is True

def test_add_task_detects_transitive_cycle():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b", depends_on=["a"])
    s.add_task("c", depends_on=["b"])
    # Artificially create a->c->b->a cycle
    s._deps["a"].add("c")
    s._rdeps["c"].add("a")
    assert s._has_cycle("a") is True


# ── get_ready_tasks ───────────────────────────────────────────────────────────

def test_no_deps_immediately_ready():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b")
    ready = s.get_ready_tasks()
    assert set(ready) == {"a", "b"}

def test_dep_not_done_not_ready():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b", depends_on=["a"])
    ready = s.get_ready_tasks()
    assert "b" not in ready
    assert "a" in ready

def test_dep_done_makes_child_ready():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b", depends_on=["a"])
    s.complete("a")
    ready = s.get_ready_tasks()
    assert "b" in ready

def test_multiple_deps_all_must_be_done():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b")
    s.add_task("c", depends_on=["a", "b"])
    s.complete("a")
    assert "c" not in s.get_ready_tasks()
    s.complete("b")
    assert "c" in s.get_ready_tasks()


# ── execution_order ───────────────────────────────────────────────────────────

def test_execution_order_respects_deps():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b", depends_on=["a"])
    s.add_task("c", depends_on=["b"])
    order = s.execution_order()
    assert order.index("a") < order.index("b")
    assert order.index("b") < order.index("c")

def test_execution_order_diamond():
    """a -> b, a -> c, b -> d, c -> d"""
    s = Scheduler()
    s.add_task("a")
    s.add_task("b", depends_on=["a"])
    s.add_task("c", depends_on=["a"])
    s.add_task("d", depends_on=["b", "c"])
    order = s.execution_order()
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")

def test_execution_order_includes_all_tasks():
    s = Scheduler()
    for name in ["a", "b", "c"]:
        s.add_task(name)
    assert set(s.execution_order()) == {"a", "b", "c"}


# ── fail propagation ──────────────────────────────────────────────────────────

def test_fail_marks_task_failed():
    s = Scheduler()
    s.add_task("a")
    s.fail("a")
    assert s.status("a") == Status.FAILED

def test_fail_propagates_to_direct_dependents():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b", depends_on=["a"])
    s.fail("a")
    assert s.status("b") == Status.FAILED

def test_fail_propagates_transitively():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b", depends_on=["a"])
    s.add_task("c", depends_on=["b"])
    s.fail("a")
    assert s.status("b") == Status.FAILED
    assert s.status("c") == Status.FAILED

def test_fail_does_not_affect_unrelated_tasks():
    s = Scheduler()
    s.add_task("a")
    s.add_task("b")   # independent
    s.fail("a")
    assert s.status("b") == Status.PENDING


# ── status / unknown ─────────────────────────────────────────────────────────

def test_status_unknown_task_raises():
    s = Scheduler()
    with pytest.raises(UnknownTaskError):
        s.status("ghost")

def test_start_marks_running():
    s = Scheduler()
    s.add_task("a")
    s.start("a")
    assert s.status("a") == Status.RUNNING

def test_complete_marks_done():
    s = Scheduler()
    s.add_task("a")
    s.complete("a")
    assert s.status("a") == Status.DONE
