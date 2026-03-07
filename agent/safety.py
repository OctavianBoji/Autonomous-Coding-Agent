from __future__ import annotations

from typing import Iterable
import ast

from .schemas import Patch


_BLOCKED_SUBSTRINGS: tuple[str, ...] = (
    "os.system",
    "subprocess.",
    "socket.",
    "requests.",
    "urllib.",
    "eval(",
    "exec(",
    "shutil.rmtree",
)

_BLOCKED_IMPORT_MODULES: tuple[str, ...] = (
    "subprocess",
    "socket",
    "requests",
    "urllib",
)

_BLOCKED_CALL_NAMES: tuple[str, ...] = (
    "eval",
    "exec",
    "__import__",
)


def _patch_text(patch: Patch) -> str:
    if patch.new_content is not None:
        return patch.new_content
    if patch.unified_diff is not None:
        return patch.unified_diff
    return ""


def _extract_python_from_diff(diff_text: str) -> str:
    """
    Very small helper to approximate the resulting Python code from a unified
    diff by concatenating added and context lines.
    """
    lines: list[str] = []
    for raw in diff_text.splitlines():
        if not raw:
            continue
        if raw.startswith(("---", "+++", "@@")):
            continue
        tag = raw[0]
        if tag in (" ", "+"):
            lines.append(raw[1:])
    return "\n".join(lines)


def _is_python_file(patch: Patch) -> bool:
    return patch.relative_path.endswith(".py")


def _ast_is_safe_python(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fall back to substring checks handled by the caller.
        return True

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _BLOCKED_IMPORT_MODULES:
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _BLOCKED_IMPORT_MODULES:
                return False
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _BLOCKED_CALL_NAMES:
                return False
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id in ("os", "subprocess", "socket", "requests", "urllib"):
                    return False

    return True


def patches_are_safe(patches: Iterable[Patch]) -> bool:
    """
    Static safety check for generated patches.

    We conservatively scan the patch payloads (either full content or unified
    diffs) for obviously dangerous operations and also perform an AST-level
    inspection for Python files. Writes outside the workspace are enforced
    separately by the patching module.
    """

    for patch in patches:
        text = _patch_text(patch)
        # Fast substring check on raw payload.
        for blocked in _BLOCKED_SUBSTRINGS:
            if blocked in text:
                return False

        # AST-level check for Python files when we can approximate the result.
        if _is_python_file(patch):
            if patch.new_content is not None:
                candidate_code = patch.new_content
            elif patch.unified_diff is not None:
                candidate_code = _extract_python_from_diff(patch.unified_diff)
            else:
                candidate_code = ""

            if candidate_code and not _ast_is_safe_python(candidate_code):
                return False

    return True

