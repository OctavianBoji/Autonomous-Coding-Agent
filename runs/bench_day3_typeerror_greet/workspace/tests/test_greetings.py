from __future__ import annotations

from greetings import greet


def test_greet_accepts_name() -> None:
    assert greet("Alice") == "Hello, Alice!"

