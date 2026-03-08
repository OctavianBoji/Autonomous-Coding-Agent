"""
Task Scheduler with dependency resolution.

Manages a directed acyclic graph (DAG) of tasks.
Tasks may only execute once all their dependencies are complete.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Set


class Status(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class CycleError(Exception):
    """Raised when a dependency cycle is detected."""


class UnknownTaskError(Exception):
    """Raised when referencing a task that does not exist."""


class Scheduler:
    def __init__(self) -> None:
        self._tasks: Dict[str, Status] = {}
        self._deps: Dict[str, Set[str]] = {}   # task -> set of tasks it depends on
        self._rdeps: Dict[str, Set[str]] = {}  # task -> set of tasks that depend on it

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_task(self, name: str, depends_on: List[str] | None = None) -> None:
        """Register a task. Raises UnknownTaskError if any dependency is unknown.
        Raises CycleError if adding this task would create a cycle."""
        if name in self._tasks:
            return  # idempotent

        deps = set(depends_on or [])
        for d in deps:
            if d not in self._tasks:
                raise UnknownTaskError(f"Dependency '{d}' not registered.")

        self._tasks[name] = Status.PENDING
        self._deps[name] = deps
        self._rdeps[name] = set()

        for d in deps:
            self._rdeps[d].add(name)

        # BUG 1: _has_cycle is never actually called — cycles are never detected.
        # (The call below is commented out so the bug is silent.)
        # if self._has_cycle(name):
        #     ...

    def _has_cycle(self, start: str) -> bool:
        """Return True if there is a cycle reachable from start.
        BUG 2: Uses the wrong visited set — checks _rdeps instead of _deps,
        so it traverses dependents (children) rather than dependencies (parents)
        and never detects real cycles."""
        visited: Set[str] = set()
        stack: List[str] = [start]
        while stack:
            node = stack.pop()
            if node in visited:
                return True
            visited.add(node)
            # Should traverse _deps[node] to follow dependency edges backward,
            # but traverses _rdeps[node] instead.
            stack.extend(self._rdeps.get(node, set()))
        return False

    # ------------------------------------------------------------------
    # Scheduling queries
    # ------------------------------------------------------------------

    def get_ready_tasks(self) -> List[str]:
        """Return tasks whose dependencies are all DONE and are themselves PENDING.
        BUG 3: checks Status.READY instead of Status.DONE for dependencies,
        so tasks whose deps are DONE are never considered ready."""
        result = []
        for name, status in self._tasks.items():
            if status != Status.PENDING:
                continue
            if all(self._tasks[d] == Status.READY for d in self._deps[name]):
                result.append(name)
        return result

    def execution_order(self) -> List[str]:
        """Return a valid topological order for all tasks.
        BUG 4: iterates over _rdeps instead of _deps when computing in-degrees,
        producing a reversed / incorrect ordering."""
        in_degree: Dict[str, int] = {t: 0 for t in self._tasks}
        for task in self._tasks:
            # Should be: for dep in self._deps[task]: in_degree[task] += 1
            # But instead counts rdeps (outgoing edges), not deps (incoming edges).
            for _ in self._rdeps[task]:
                in_degree[task] += 1

        queue = [t for t, deg in in_degree.items() if deg == 0]
        order: List[str] = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for dependent in self._rdeps[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        return order

    # ------------------------------------------------------------------
    # Status management
    # ------------------------------------------------------------------

    def start(self, name: str) -> None:
        """Mark a task as RUNNING. Raises if not PENDING."""
        if name not in self._tasks:
            raise UnknownTaskError(name)
        self._tasks[name] = Status.RUNNING

    def complete(self, name: str) -> None:
        """Mark a task as DONE."""
        if name not in self._tasks:
            raise UnknownTaskError(name)
        self._tasks[name] = Status.DONE

    def fail(self, name: str) -> None:
        """Mark a task and all its transitive dependents as FAILED.
        BUG 5: only marks the task itself; does not propagate failure
        to tasks that depend on it."""
        if name not in self._tasks:
            raise UnknownTaskError(name)
        self._tasks[name] = Status.FAILED

    def status(self, name: str) -> Status:
        if name not in self._tasks:
            raise UnknownTaskError(name)
        return self._tasks[name]
