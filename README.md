## Self-Improving Coding Agent

This repository implements a **deterministic autonomous coding agent**, not a chatbot. Given a
task JSON file that points at a small Python project with failing tests, the agent:

- Copies the project into an isolated workspace.
- Iteratively plans, applies code patches, runs tests, and reflects.
- Persists every step to SQLite and a JSONL trace for full auditability.

The core loop is:

- **plan → safety_check → apply_patches → test → reflect → next plan**

LLM integration is optional and **disabled by default**; the default behavior is fully offline
and heuristic-driven.

### Architecture overview

- **`agent.cli`**: CLI entrypoint (`python -m agent ...`).
- **`agent.controller`**: Orchestrates the Plan→Execute→Test→Reflect loop, circuit breakers,
  and resumability.
- **`agent.executor`**: Runs tests inside the workspace via `python -m pytest -q` with a hard
  timeout.
- **`agent.patching`**: Applies `Patch` objects safely inside the workspace with atomic writes
  and full diff/hashing audit fields.
- **`agent.reflection`**: Deterministic heuristics that analyze test output and emit a
  structured `Reflection` (`error_signature`, `root_cause`, `fix_plan`).
- **`agent.safety`**: Static safety checks over patch payloads (substring + AST-based checks).
- **`agent.model`**: `ModelProvider` abstraction with a default `HeuristicModelProvider` and an
  optional `OpenAIModelProvider`.
- **`agent.persistence`**: SQLite schema and helpers (`runs`, `iterations`, `patches`,
  `test_results`, `reflections`).
- **`agent.tracing`**: Append-only JSONL trace events per run.
- **`agent.eval`**: Benchmark/evaluation runner over `tasks/bench`.

All schemas are defined with pydantic in `agent.schemas`.

### Safety model

- **Workspace-only writes**: All patching is constrained to paths under the per-run workspace
  (`runs/<task_id>/workspace`); path escapes are rejected.
- **Static content checks**: Every patch (`new_content` or `unified_diff`) is scanned for
  obviously dangerous patterns: `os.system`, `subprocess.*`, `socket`, `requests`, `urllib`,
  `eval`, `exec`, `shutil.rmtree`, etc.
- **AST-based Python checks**: For Python files, the agent parses the candidate code and blocks:
  - Imports of `subprocess`, `socket`, `requests`, `urllib`.
  - Calls to `eval`, `exec`, `__import__`.
  - Attribute calls on `os`, `subprocess`, `socket`, `requests`, `urllib`.
- **Execution sandboxing**:
  - Tests run with `cwd` set to the workspace root.
  - Tests are executed as `sys.executable -m pytest -q` with a hard timeout.
  - Untrusted code is never executed outside the workspace.
- **Unsafe patches**: If any patch fails safety checks, the iteration is marked `unsafe_patch`,
  the run stops, and the summary explains that patches were rejected as unsafe.

### Observability and auditability

For each run `runs/<task_id>/` contains:

- `workspace/`: Isolated copy of the target project plus any patches applied.
- `run.db`: SQLite database with:
  - `runs`: high-level run metadata.
  - `iterations`: status, timestamps, `plan_json`, `stop_reason`.
  - `patches`: `relative_path`, `new_content`, `unified_diff`, computed `diff_text`,
    `before_sha256`, `after_sha256`.
  - `test_results`: `success`, `exit_code`, `duration_seconds`, `duration_ms`, `stdout`,
    `stderr`, `command`, `cwd`.
  - `reflections`: `error_signature`, `root_cause`, `fix_plan_json`,
    `normalized_error_text`.
- `trace.jsonl`: Stream of structured events:
  - `iteration_start`
  - `plan_generated`
  - `safety_checked`
  - `patches_applied`
  - `tests_completed`
  - `reflection_generated`
  - `iteration_end` (`status`, `stop_reason`)
- `summary.md`: Human-readable summary with goal, status, iterations, and latest test output.

This makes every decision (plan, patch, test result, reflection) auditable post-hoc.

### Running the agent (offline heuristic mode)

1. **Install dependencies** (Python 3.11+ recommended) and activate a virtualenv.
2. Run unit tests:

```bash
python -m pytest
```

3. Run a single task:

```bash
python -m agent run --task tasks/sample_task_fixable.json --max-iters 8
```

This will:

- Create `runs/sample_task_fixable/workspace/` with a copy of `tasks/sample_project_fixable/`.
- Run tests via `python -m pytest -q` inside the workspace with a timeout.
- Iterate with deterministic heuristic reflections until tests pass or limits are reached.
- Populate `run.db`, `trace.jsonl`, and `summary.md`.

4. Run the benchmark/evaluation suite:

```bash
python -m agent eval --tasks tasks/bench --max-iters 8
```

This discovers all `tasks/bench/*.json`, runs the agent for each, prints a tab-separated table
(task_id, PASS/FAIL, iterations, time_ms, final_status), and writes `runs/eval_<timestamp>.json`
with full metrics.

### Optional LLM mode (disabled by default)

By default, the agent uses `HeuristicModelProvider` and **does not call any external APIs**.
To enable the optional OpenAI-backed provider later:

1. Copy `.env.example` to `.env` and fill in:

```text
OPENAI_API_KEY=sk-...
MODEL_PROVIDER=openai
```

2. Ensure your environment loader (e.g. `python-dotenv` in your shell, or export variables
manually) makes these variables available to the process.

3. Re-run the same commands (`agent run` / `agent eval`). The controller will now obtain its
`ModelProvider` from `agent.model.get_model_provider`, which selects `OpenAIModelProvider`
only when `MODEL_PROVIDER=openai` and `OPENAI_API_KEY` is set; otherwise it stays on the
heuristic provider.

All safety checks and workspace constraints remain in effect for LLM-generated patches.

### Limitations

- **No container sandbox**: Execution is constrained to a per-run workspace directory and a
  pytest timeout; there is no Docker or VM sandbox.
- **Python-only projects**: The agent is designed for small Python projects with pytest tests.
- **Deterministic heuristics**: The offline mode uses hand-written heuristics for specific
  error patterns (assertion mismatches, missing args, missing attributes/names, missing local
  modules). Not all failures are automatically fixable.
- **Single-machine SQLite**: Persistence uses a local SQLite file per run; there is no
  multi-user or distributed coordination.

