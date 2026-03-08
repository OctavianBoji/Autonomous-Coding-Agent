class Status:
    PENDING = "pending"
    DONE = "done"
    RUNNING = "running"
    FAILED = "failed"

class CycleError(Exception):
    pass

class UnknownTaskError(Exception):
    pass

class Scheduler:
    def __init__(self):
        from collections import defaultdict
        self._deps = defaultdict(set)  # Maps task -> its dependencies
        self._rdeps = defaultdict(set)  # Maps task -> its dependents
        self._status = defaultdict(lambda: Status.PENDING)

    def add_task(self, task_name, depends_on=None):
        depends_on = depends_on or []

        # Check for unknown dependencies
        for dep in depends_on:
            if dep not in self._deps:
                raise UnknownTaskError(f"Task {dep} does not exist.")
        
        if task_name in self._deps:
            self._deps[task_name].update(depends_on)
        else:
            self._deps[task_name] = set(depends_on)

        for dep_task in depends_on:
            self._rdeps[dep_task].add(task_name)

        # Detect cycles
        if self._has_cycle(task_name):
            # Roll back changes if cycle is detected
            self._deps[task_name].difference_update(depends_on)
            for dep_task in depends_on:
                self._rdeps[dep_task].remove(task_name)
            raise CycleError(f"Adding {task_name} creates a cycle.")

    def _has_cycle(self, start):
        visited = set()
        stack = set()

        def visit(node):
            if node in visited:
                return False
            if node in stack:
                return True  # Cycle detected

            stack.add(node)
            for neighbour in self._deps[node]:  # Correctly traverse dependencies
                if visit(neighbour):
                    return True

            stack.remove(node)
            visited.add(node)
            return False

        return visit(start)

    def get_ready_tasks(self):
        return [task for task, deps in self._deps.items()
                if self._status[task] == Status.PENDING and
                all(self._status[d] == Status.DONE for d in deps)]  # Compare against DONE

    def execution_order(self):
        from collections import deque
        in_degree = {task: 0 for task in self._deps}

        # Traverse the dependencies to calculate in-degree
        for task, deps in self._deps.items():
            for dep in deps:
                in_degree[task] += 1  # Correct calculation of incoming edges

        queue = deque([t for t, degree in in_degree.items() if degree == 0])  # Start with nodes with no incoming edges
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)

            for dependent in self._rdeps[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(self._deps):
            raise CycleError("Graph has at least one cycle")

        return order

    def fail(self, task_name):
        self._status[task_name] = Status.FAILED

        def propagate_failure(task_name):
            # Fail all dependents if they aren't already failed
            for dep in self._rdeps[task_name]:
                if self._status[dep] != Status.FAILED:
                    self._status[dep] = Status.FAILED
                    propagate_failure(dep)

        propagate_failure(task_name)

    def status(self, task_name):
        if task_name not in self._deps:
            raise UnknownTaskError(f"Unknown task {task_name}")
        return self._status[task_name]

    def start(self, task_name):
        if self._status[task_name] == Status.PENDING:
            self._status[task_name] = Status.RUNNING

    def complete(self, task_name):
        if task_name not in self._deps:
            raise UnknownTaskError(f"Unknown task {task_name}")
        # Correct the task status update
        if self._status[task_name] in [Status.RUNNING, Status.PENDING]:
            self._status[task_name] = Status.DONE
