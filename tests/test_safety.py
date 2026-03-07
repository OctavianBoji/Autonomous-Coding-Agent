from __future__ import annotations

from agent.safety import patches_are_safe
from agent.schemas import Patch


def test_patches_are_safe_for_benign_code() -> None:
    patch = Patch(relative_path="safe.py", new_content="x = 1\n", unified_diff=None)
    assert patches_are_safe([patch]) is True


def test_patches_are_unsafe_when_blocked_calls_present_in_new_content() -> None:
    patch = Patch(
        relative_path="danger.py",
        new_content="import os\nos.system('rm -rf /')\n",
        unified_diff=None,
    )
    assert patches_are_safe([patch]) is False


def test_patches_are_unsafe_when_blocked_calls_present_in_unified_diff() -> None:
    diff = (
        "--- a/danger.py\n"
        "+++ b/danger.py\n"
        "@@ -1,1 +1,2 @@\n"
        "-x = 1\n"
        "+import subprocess\n"
        "+subprocess.Popen(['ls'])\n"
    )
    patch = Patch(relative_path="danger.py", new_content=None, unified_diff=diff)
    assert patches_are_safe([patch]) is False


def test_patches_are_unsafe_via_ast_for_python_new_content() -> None:
    patch = Patch(
        relative_path="danger_ast.py",
        new_content="import subprocess\nsubprocess.call(['ls'])\n",
        unified_diff=None,
    )
    assert patches_are_safe([patch]) is False


def test_patches_are_unsafe_via_ast_for_python_unified_diff() -> None:
    diff = (
        "--- a/danger_ast.py\n"
        "+++ b/danger_ast.py\n"
        "@@ -1,1 +1,3 @@\n"
        "-x = 1\n"
        "+import socket\n"
        "+socket.socket()\n"
    )
    patch = Patch(relative_path="danger_ast.py", new_content=None, unified_diff=diff)
    assert patches_are_safe([patch]) is False

