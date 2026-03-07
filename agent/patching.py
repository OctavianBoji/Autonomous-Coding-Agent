from __future__ import annotations

from pathlib import Path
from typing import Iterable
import hashlib
import difflib

from .persistence import insert_patch
from .schemas import Patch
from .workspace import RunPaths


def _ensure_within_workspace(workspace_root: Path, target: Path) -> None:
    """
    Ensure the target path is within the workspace_root.

    This guards against accidentally writing outside the sandbox.
    """
    workspace_root_resolved = workspace_root.resolve()
    target_resolved = target.resolve()
    if not str(target_resolved).startswith(str(workspace_root_resolved)):
        raise ValueError(f"Refusing to write outside workspace: {target_resolved}")


def _write_atomic(path: Path, content: str) -> None:
    """Atomically write content to a file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def _apply_unified_diff(original: str, diff_text: str) -> str:
    """
    Apply a minimal unified diff to the original text.

    This implementation intentionally supports a constrained subset of unified
    diffs sufficient for our benchmark tasks:
    - Single-file diffs with one or more hunks.
    - Standard @@ -l,s +l2,s2 @@ hunk headers.
    """
    lines = original.splitlines(keepends=False)
    diff_lines = diff_text.splitlines(keepends=False)
    
    idx = 0
    # Skip file headers and any blank separator lines until the first hunk header.
    while idx < len(diff_lines) and (
        diff_lines[idx].startswith("---")
        or diff_lines[idx].startswith("+++")
        or diff_lines[idx].strip() == ""
    ):
        idx += 1

    result: list[str] = []
    orig_index = 0

    while idx < len(diff_lines):
        # Skip blank lines between hunks / after hunk headers (diff generators sometimes include them).
        while idx < len(diff_lines) and diff_lines[idx].strip() == "":
            idx += 1
        if idx >= len(diff_lines):
            break
        header = diff_lines[idx]
        if not header.startswith("@@"):
            raise ValueError("Invalid unified diff: expected hunk header.")
        idx += 1

        # Parse hunk header: @@ -l,s +l2,s2 @@
        try:
            header_core = header.split("@@")[1].strip()
            minus_part, plus_part = header_core.split(" ")[:2]
            minus_start = int(minus_part.split(",")[0].lstrip("-"))
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid hunk header: {header}") from exc

        # Copy unchanged lines up to the hunk start.
        minus_start_index = minus_start - 1
        if minus_start_index < orig_index:
            raise ValueError("Overlapping hunks are not supported.")
        result.extend(lines[orig_index:minus_start_index])
        orig_index = minus_start_index

        # Apply hunk body.
        while idx < len(diff_lines) and not diff_lines[idx].startswith("@@"):
            line = diff_lines[idx]
            idx += 1
            if not line:
                continue
            tag = line[0]
            content = line[1:]
            if tag == " ":
                # Context line: must match original.
                if orig_index >= len(lines):
                    raise ValueError("Context line out of range in original content.")
                # We do not enforce exact text match to keep implementation simple.
                result.append(lines[orig_index])
                orig_index += 1
            elif tag == "-":
                # Removal: skip line from original.
                if orig_index >= len(lines):
                    raise ValueError("Removal line out of range in original content.")
                orig_index += 1
            elif tag == "+":
                # Addition: append new line.
                result.append(content)
            else:
                raise ValueError(f"Unexpected diff line tag: {tag!r}")

    # Append any remaining original lines after the last hunk.
    result.extend(lines[orig_index:])

    return "\n".join(result) + ("\n" if original.endswith("\n") else "")


def apply_patches(run_paths: RunPaths, iteration_id: int, patches: Iterable[Patch]) -> None:
    """
    Apply a sequence of patches to the workspace for a given iteration.

    Supports both full-content (`new_content`) and `unified_diff` patches.
    """
    workspace_root = run_paths.workspace_root

    for patch in patches:
        target = (workspace_root / patch.relative_path).resolve()
        _ensure_within_workspace(workspace_root, target)

        if patch.new_content is not None:
            original = target.read_text(encoding="utf-8") if target.exists() else ""
            content_to_write = patch.new_content
        elif patch.unified_diff is not None:
            original = target.read_text(encoding="utf-8") if target.exists() else ""
            content_to_write = _apply_unified_diff(original, patch.unified_diff)
        else:  # pragma: no cover - guarded by Patch model
            raise ValueError("Patch must have either new_content or unified_diff.")

        before_bytes = original.encode("utf-8")
        after_bytes = content_to_write.encode("utf-8")
        before_sha256 = hashlib.sha256(before_bytes).hexdigest()
        after_sha256 = hashlib.sha256(after_bytes).hexdigest()

        if patch.new_content is not None:
            before_lines = original.splitlines(keepends=False)
            after_lines = content_to_write.splitlines(keepends=False)
            diff_lines = list(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=patch.relative_path,
                    tofile=patch.relative_path,
                )
            )
            diff_text = "\n".join(diff_lines) + ("\n" if diff_lines else "")
        else:
            diff_text = patch.unified_diff or ""

        _write_atomic(target, content_to_write)
        insert_patch(
            run_paths.db_path,
            iteration_id=iteration_id,
            patch=patch,
            diff_text=diff_text,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
        )

