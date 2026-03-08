from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .executor import run_tests
from .model import get_model_provider
from .patching import apply_patches
from .persistence import (
    ensure_run_record,
    init_db,
    insert_iteration,
    insert_reflection,
    insert_test_result,
    update_iteration_plan,
    update_iteration_status,
    update_iteration_stop_reason,
)
from .schemas import Plan, TaskConfig, Reflection
from .safety import patches_are_safe
from .tracing import log_event
from .workspace import RunPaths, copy_repo_to_workspace, prepare_run_directories


def _load_task(task_path: Path) -> TaskConfig:
    import json

    data = json.loads(task_path.read_text(encoding="utf-8"))
    return TaskConfig.model_validate(data)


def _initial_plan(task: TaskConfig) -> Plan:
    """
    Backwards-compatible helper that defers to the active model provider.
    """
    provider = get_model_provider()
    return provider.generate_initial_plan(task)


def _write_summary(
    paths: RunPaths,
    *,
    task: TaskConfig,
    status: str,
    test_output: str,
    run_id: str,
    iteration_index: int,
) -> None:
    content_lines = [
        f"# Run summary for {run_id}",
        "",
        f"- Goal: {task.goal}",
        f"- Status: {status}",
        f"- Iterations completed: {iteration_index + 1}",
        "",
        "## Latest test output",
        "",
        "```",
        test_output,
        "```",
        "",
    ]
    paths.summary_path.write_text("\n".join(content_lines), encoding="utf-8")


def _log(msg: str) -> None:
    print(f"[agent] {msg}", flush=True)


def run_task(task_path: Path, max_iterations: int | None = None) -> None:
    """Run the agent loop for up to `max_iterations` iterations."""
    task = _load_task(task_path)
    _log(f"Task loaded: {task_path.name}")
    _log(f"Goal: {task.goal[:80]}{'...' if len(task.goal) > 80 else ''}")

    run_paths = prepare_run_directories(task_path)
    run_id = run_paths.run_id
    _log(f"Run ID: {run_id}  |  workspace: {run_paths.workspace_root}")

    # Initialize persistence and determine whether this is a fresh run or a resume.
    is_resume = run_paths.db_path.exists()
    init_db(run_paths.db_path)
    created_at = datetime.now(timezone.utc).isoformat()
    ensure_run_record(run_paths.db_path, run_id=run_id, goal=task.goal, created_at=created_at)

    # Prepare workspace only for fresh runs; resume keeps the existing workspace.
    if not is_resume:
        repo_src = task.resolved_repo_path(task_path)
        _log(f"Copying repo from {repo_src} → workspace")
        copy_repo_to_workspace(repo_src, run_paths.workspace_root)
    else:
        _log("Resuming existing run (workspace preserved)")

    max_iters = max_iterations or settings.default_max_iterations
    if max_iters < 1:
        max_iters = 1

    provider = get_model_provider()
    _log(f"Model provider: {type(provider).__name__}")
    _log(f"Max iterations: {max_iters}")
    print(flush=True)

    last_error_signature: str | None = None
    repeat_count = 0
    final_status = "FAIL"
    latest_test_output = ""
    next_plan: Plan | None = None
    history: list[Reflection] = []

    for iteration_index in range(max_iters):
        _log(f"{'─' * 50}")
        _log(f"Iteration {iteration_index + 1}/{max_iters}")
        log_event(
            run_paths.trace_path,
            event_type="iteration_start",
            run_id=run_id,
            iteration_index=iteration_index,
            payload={"goal": task.goal},
        )

        iteration_id = insert_iteration(
            run_paths.db_path,
            run_id=run_id,
            iteration_index=iteration_index,
            status="running",
            created_at=created_at,
        )

        if next_plan is not None:
            _log("  Using fix plan from previous reflection")
            plan = next_plan
            next_plan = None
        else:
            _log("  Calling generate_initial_plan() → LLM reads workspace files")
            plan = provider.generate_initial_plan(task, workspace_root=run_paths.workspace_root)

        _log(f"  Plan: \"{plan.description[:70]}\"")
        _log(f"  Patches proposed: {len(plan.patches)}" +
             (f" → {[p.relative_path for p in plan.patches]}" if plan.patches else " (none)"))

        update_iteration_plan(run_paths.db_path, iteration_id, plan.model_dump_json())

        log_event(
            run_paths.trace_path,
            event_type="plan_generated",
            run_id=run_id,
            iteration_index=iteration_index,
            payload=plan.model_dump(),
        )

        _log("  Calling patches_are_safe() → safety check")
        safe = patches_are_safe(plan.patches)
        _log(f"  Safety result: {'SAFE' if safe else 'UNSAFE'}")
        log_event(
            run_paths.trace_path,
            event_type="safety_checked",
            run_id=run_id,
            iteration_index=iteration_index,
            payload={"patch_count": len(plan.patches), "safe": safe},
        )
        if not safe:
            update_iteration_status(run_paths.db_path, iteration_id, status="unsafe_patch")
            update_iteration_stop_reason(run_paths.db_path, iteration_id, "unsafe_patch")
            final_status = "unsafe_patch"
            latest_test_output = "Patches rejected as unsafe."
            log_event(
                run_paths.trace_path,
                event_type="iteration_end",
                run_id=run_id,
                iteration_index=iteration_index,
                payload={"status": "unsafe_patch", "stop_reason": "unsafe_patch"},
            )
            _write_summary(
                run_paths,
                task=task,
                status=final_status,
                test_output=latest_test_output,
                run_id=run_id,
                iteration_index=iteration_index,
            )
            return

        if plan.patches:
            _log(f"  Calling apply_patches() → writing {len(plan.patches)} file(s)")
            apply_patches(run_paths, iteration_id=iteration_id, patches=plan.patches)
            log_event(
                run_paths.trace_path,
                event_type="patches_applied",
                run_id=run_id,
                iteration_index=iteration_index,
                payload={"patch_count": len(plan.patches)},
            )

        _log(f"  Calling run_tests() → {task.test_command or settings.default_test_command}")
        test_result = run_tests(
            run_paths.workspace_root,
            test_command=task.test_command or settings.default_test_command,
            timeout_seconds=settings.pytest_timeout_seconds,
        )
        insert_test_result(run_paths.db_path, iteration_id=iteration_id, result=test_result)

        log_event(
            run_paths.trace_path,
            event_type="tests_completed",
            run_id=run_id,
            iteration_index=iteration_index,
            payload=test_result.model_dump(),
        )

        latest_test_output = (test_result.stdout + "\n" + test_result.stderr).strip()
        _log(f"  Tests: {'PASS ✓' if test_result.success else 'FAIL ✗'}  (exit={test_result.exit_code}, {test_result.duration_ms}ms)")

        if test_result.success:
            update_iteration_status(run_paths.db_path, iteration_id, status="success")
            update_iteration_stop_reason(run_paths.db_path, iteration_id, "success")
            final_status = "PASS"
            log_event(
                run_paths.trace_path,
                event_type="iteration_end",
                run_id=run_id,
                iteration_index=iteration_index,
                payload={"status": "success", "stop_reason": "success"},
            )
            _log(f"\n  ══ DONE: all tests passed in {iteration_index + 1} iteration(s) ══")
            _write_summary(
                run_paths,
                task=task,
                status=final_status,
                test_output=latest_test_output,
                run_id=run_id,
                iteration_index=iteration_index,
            )
            return

        # Failed tests: generate reflection and possibly trip the circuit breaker.
        _log("  Calling reflect_and_propose() → LLM analyses failures")
        reflection = provider.reflect_and_propose(
            task=task,
            test_result=test_result,
            history=history,
            workspace_root=run_paths.workspace_root,
        )
        # Use the reflection's concrete fix plan as the starting point for
        # the next iteration.
        next_plan = reflection.fix_plan
        _log(f"  Root cause: \"{reflection.root_cause[:80]}\"")
        _log(f"  Fix plan: \"{reflection.fix_plan.description[:70]}\"")
        _log(f"  Patches in fix plan: {len(reflection.fix_plan.patches)}" +
             (f" → {[p.relative_path for p in reflection.fix_plan.patches]}" if reflection.fix_plan.patches else " (none)"))
        insert_reflection(run_paths.db_path, iteration_id=iteration_id, reflection=reflection)
        history.append(reflection)

        log_event(
            run_paths.trace_path,
            event_type="reflection_generated",
            run_id=run_id,
            iteration_index=iteration_index,
            payload={
                "error_signature": reflection.error_signature,
                "root_cause": reflection.root_cause,
            },
        )

        if last_error_signature == reflection.error_signature:
            repeat_count += 1
        else:
            repeat_count = 1

        _log(f"  Error signature: {reflection.error_signature}  (repeat count: {repeat_count})")
        if repeat_count >= settings.circuit_breaker_repeats:
            # Circuit breaker: same failure signature repeated too many times.
            update_iteration_status(
                run_paths.db_path,
                iteration_id,
                status="aborted_repeated_failure",
            )
            update_iteration_stop_reason(run_paths.db_path, iteration_id, "repeated_failure")
            final_status = "aborted_repeated_failure"
            _log(f"\n  ══ CIRCUIT BREAKER: same error repeated {repeat_count}x — aborting ══")
            log_event(
                run_paths.trace_path,
                event_type="iteration_end",
                run_id=run_id,
                iteration_index=iteration_index,
                payload={
                    "status": "aborted_repeated_failure",
                    "stop_reason": "repeated_failure",
                    "error_signature": reflection.error_signature,
                },
            )
            _write_summary(
                run_paths,
                task=task,
                status=final_status,
                test_output=latest_test_output,
                run_id=run_id,
                iteration_index=iteration_index,
            )
            return

        # Mark this iteration as failed and continue if budget remains.
        update_iteration_status(run_paths.db_path, iteration_id, status="failed")
        last_error_signature = reflection.error_signature

    # Exhausted all iterations without success.
    # Exhausted all iterations without success.
    last_index = max_iters - 1
    if last_index >= 0:
        # Best-effort: mark the last iteration with a max_iters stop reason.
        # This is conservative; if fewer iterations actually ran, the DB will
        # simply not contain that iteration id.
        # Detailed run/iteration inspection is still possible via the DB.
        pass

    _write_summary(
        run_paths,
        task=task,
        status=final_status,
        test_output=latest_test_output,
        run_id=run_id,
        iteration_index=last_index,
    )

