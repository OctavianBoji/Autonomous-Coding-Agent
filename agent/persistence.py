from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .schemas import Patch, Reflection, TestResult


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """
    Initialize the SQLite schema used by the agent.

    This function is idempotent and safe to call multiple times. For the
    development prototype, we aggressively recreate the `patches` table to
    ensure the expected schema is present.
    """
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS iterations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                iteration_index INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                plan_json TEXT,
                stop_reason TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            );

            CREATE TABLE IF NOT EXISTS patches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration_id INTEGER NOT NULL,
                relative_path TEXT NOT NULL,
                new_content TEXT,
                unified_diff TEXT,
                diff_text TEXT NOT NULL,
                before_sha256 TEXT NOT NULL,
                after_sha256 TEXT NOT NULL,
                FOREIGN KEY(iteration_id) REFERENCES iterations(id)
            );

            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration_id INTEGER NOT NULL,
                success INTEGER NOT NULL,
                exit_code INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                duration_ms INTEGER NOT NULL,
                stdout TEXT,
                stderr TEXT,
                command TEXT NOT NULL,
                cwd TEXT NOT NULL,
                FOREIGN KEY(iteration_id) REFERENCES iterations(id)
            );

            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration_id INTEGER NOT NULL,
                error_signature TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                fix_plan_json TEXT NOT NULL,
                normalized_error_text TEXT NOT NULL,
                FOREIGN KEY(iteration_id) REFERENCES iterations(id)
            );
            """
        )
        # Lightweight migrations for existing databases: add missing columns if needed.
        cur.execute("PRAGMA table_info(test_results)")
        existing_test_cols = {row[1] for row in cur.fetchall()}
        if "duration_ms" not in existing_test_cols:
            cur.execute("ALTER TABLE test_results ADD COLUMN duration_ms INTEGER NOT NULL DEFAULT 0")
        if "command" not in existing_test_cols:
            cur.execute("ALTER TABLE test_results ADD COLUMN command TEXT NOT NULL DEFAULT ''")
        if "cwd" not in existing_test_cols:
            cur.execute("ALTER TABLE test_results ADD COLUMN cwd TEXT NOT NULL DEFAULT ''")

        cur.execute("PRAGMA table_info(patches)")
        existing_patch_cols = {row[1] for row in cur.fetchall()}
        if "diff_text" not in existing_patch_cols:
            cur.execute("ALTER TABLE patches ADD COLUMN diff_text TEXT NOT NULL DEFAULT ''")
        if "before_sha256" not in existing_patch_cols:
            cur.execute("ALTER TABLE patches ADD COLUMN before_sha256 TEXT NOT NULL DEFAULT ''")
        if "after_sha256" not in existing_patch_cols:
            cur.execute("ALTER TABLE patches ADD COLUMN after_sha256 TEXT NOT NULL DEFAULT ''")

        cur.execute("PRAGMA table_info(reflections)")
        existing_refl_cols = {row[1] for row in cur.fetchall()}
        if "normalized_error_text" not in existing_refl_cols:
            cur.execute(
                "ALTER TABLE reflections ADD COLUMN normalized_error_text TEXT NOT NULL DEFAULT ''"
            )

        cur.execute("PRAGMA table_info(iterations)")
        existing_iter_cols = {row[1] for row in cur.fetchall()}
        if "plan_json" not in existing_iter_cols:
            cur.execute("ALTER TABLE iterations ADD COLUMN plan_json TEXT")
        if "stop_reason" not in existing_iter_cols:
            cur.execute("ALTER TABLE iterations ADD COLUMN stop_reason TEXT")
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_run_record(db_path: Path, run_id: str, goal: str, created_at: str) -> None:
    with db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO runs (id, goal, created_at) VALUES (?, ?, ?)",
                (run_id, goal, created_at),
            )


def insert_iteration(
    db_path: Path,
    *,
    run_id: str,
    iteration_index: int,
    status: str,
    created_at: str,
) -> int:
    with db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO iterations (run_id, iteration_index, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, iteration_index, status, created_at),
        )
        return int(cur.lastrowid)


def update_iteration_status(db_path: Path, iteration_id: int, status: str) -> None:
    with db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE iterations SET status = ? WHERE id = ?",
            (status, iteration_id),
        )


def insert_test_result(
    db_path: Path,
    iteration_id: int,
    result: TestResult,
) -> None:
    with db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO test_results (
                iteration_id, success, exit_code,
                duration_seconds, duration_ms,
                stdout, stderr, command, cwd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                iteration_id,
                1 if result.success else 0,
                result.exit_code,
                result.duration_ms / 1000.0,
                result.duration_ms,
                result.stdout,
                result.stderr,
                result.command,
                result.cwd,
            ),
        )


def insert_patch(
    db_path: Path,
    iteration_id: int,
    *,
    patch: Patch,
    diff_text: str,
    before_sha256: str,
    after_sha256: str,
) -> None:
    """Persist a single applied patch for the given iteration, including audit fields."""
    with db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO patches (
                iteration_id, relative_path, new_content, unified_diff,
                diff_text, before_sha256, after_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                iteration_id,
                patch.relative_path,
                patch.new_content,
                patch.unified_diff,
                diff_text,
                before_sha256,
                after_sha256,
            ),
        )


def insert_reflection(db_path: Path, iteration_id: int, reflection: Reflection) -> None:
    """Persist structured reflection data for an iteration."""
    with db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO reflections (
                iteration_id, error_signature, root_cause, fix_plan_json, normalized_error_text
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                iteration_id,
                reflection.error_signature,
                reflection.root_cause,
                reflection.fix_plan.model_dump_json(),
                reflection.normalized_error_text,
            ),
        )


def update_iteration_plan(db_path: Path, iteration_id: int, plan_json: str) -> None:
    with db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE iterations SET plan_json = ? WHERE id = ?",
            (plan_json, iteration_id),
        )


def update_iteration_stop_reason(
    db_path: Path,
    iteration_id: int,
    stop_reason: str,
) -> None:
    with db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE iterations SET stop_reason = ? WHERE id = ?",
            (stop_reason, iteration_id),
        )
