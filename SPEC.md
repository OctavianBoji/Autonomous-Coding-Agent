# Self-Improving Coding Agent — SPEC

## Goal
Build an autonomous coding agent that, given a goal + a failing Python project (tests), iteratively fixes the code until tests pass or limits are reached.

This is NOT a chatbot. It is a persistent, resumable, sandboxed agentic loop:
Plan → Execute (edit code) → Test → Reflect → Update memory → Repeat.

## Non-negotiable requirements
1) **Agent Loop**
- Max iterations per task (default 8)
- Circuit breaker: stop if the same failure signature repeats N times (default 2)
- Deterministic state machine: each iteration produces structured artifacts

2) **Sandboxed Execution**
- All code runs in an isolated working directory per task (`runs/<task_id>/workspace`)
- Tests run via `pytest` with a hard timeout (default 60s)
- No access outside workspace; all file ops must be constrained to workspace paths
- No network calls allowed by policy (enforced by static checks + runtime guard)

3) **Persistence + Resume**
- Every iteration persisted to SQLite (`runs/<task_id>/run.db`)
- Agent can resume a run after interruption using stored state and continue from last iteration

4) **Memory Hierarchy**
- Short-term: last 5 iterations (structured)
- Failure memory: store (error signature → root cause → fix) in a vector index + SQLite
- Retrieval: before generating the next fix, retrieve top-K similar failures and inject into prompts

5) **Reflection**
- After each failure, produce:
  - error_signature (stable hash)
  - root_cause
  - concrete_fix_plan (file-level edits)
  - “don’t repeat” rule for next step

6) **Safety**
- Static scan of generated diffs for dangerous ops:
  - os.system, subprocess, socket, requests, urllib, eval/exec, shutil.rmtree, writing outside workspace
- If unsafe: reject patch and ask model to regenerate a safe alternative

## Interfaces
### CLI
`python -m agent run --task ./tasks/<task_name>.json --max-iters 8`

### Task format (JSON)
- goal: string
- repo_path: path to a python project with failing tests OR a template to copy into workspace
- test_command: default `pytest -q`
- allowlist_paths: optional (default workspace only)

## Output artifacts
Per run:
- `runs/<task_id>/workspace/` (copied project + patches)
- `runs/<task_id>/trace.jsonl` (one JSON event per step)
- `runs/<task_id>/run.db` (SQLite)
- `runs/<task_id>/summary.md` (final report + metrics)

## Evaluation
We will run on ~20 small debugging tasks.
Metrics:
- pass/fail
- iterations to success
- repeated failure rate
- time per run

## Implementation constraints
- Python 3.11+
- Prefer standard library; minimal deps allowed: `pytest`, `pydantic`, `rich`, `sqlite-utils` (optional), `chromadb` OR `faiss-cpu`
- Clean architecture, typed code, testable modules.