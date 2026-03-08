from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from .controller import run_task
from .eval import run_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="Self-improving coding agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the agent on a task JSON file.")
    run_parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="Path to the task JSON file.",
    )
    run_parser.add_argument(
        "--max-iters",
        type=int,
        default=None,
        help="Maximum iterations to run (defaults to 8).",
    )

    eval_parser = subparsers.add_parser("eval", help="Run evaluation over a directory of task JSON files.")
    eval_parser.add_argument(
        "--tasks",
        type=str,
        required=True,
        help="Path to a directory containing task JSON files.",
    )
    eval_parser.add_argument(
        "--max-iters",
        type=int,
        default=None,
        help="Maximum iterations per task (defaults to 8).",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        task_path = Path(args.task).resolve()
        run_task(task_path, max_iterations=args.max_iters)
    elif args.command == "eval":
        tasks_dir = Path(args.tasks).resolve()
        run_evaluation(tasks_dir, max_iters=args.max_iters)
    else:  # pragma: no cover - argparse enforces choices
        parser.error(f"Unknown command: {args.command}")

