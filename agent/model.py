from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from pydantic import BaseModel

from .reflection import reflect as heuristic_reflect
from .schemas import Patch, Plan, Reflection, TaskConfig, TestResult


# ---------------------------------------------------------------------------
# Intermediate Pydantic models used only for structured LLM output parsing.
# These are simpler than the internal schemas (no cross-field validators).
# ---------------------------------------------------------------------------

class _LLMPatch(BaseModel):
    relative_path: str
    new_content: str


class _LLMPlan(BaseModel):
    description: str
    patches: List[_LLMPatch]


class _LLMReflection(BaseModel):
    error_signature: str
    root_cause: str
    normalized_error_text: str
    fix_plan: _LLMPlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_files(workspace_root: Path) -> dict[str, str]:
    """Return {relative_path: content} for every .py file in the workspace."""
    result: dict[str, str] = {}
    for path in sorted(workspace_root.rglob("*.py")):
        rel = str(path.relative_to(workspace_root))
        try:
            result[rel] = path.read_text(encoding="utf-8")
        except Exception:
            pass
    return result


def _format_files(files: dict[str, str]) -> str:
    return "\n\n".join(f"=== {k} ===\n{v}" for k, v in files.items())


def _llm_plan_to_plan(llm_plan: _LLMPlan) -> Plan:
    patches = [Patch(relative_path=p.relative_path, new_content=p.new_content) for p in llm_plan.patches]
    return Plan(description=llm_plan.description, patches=patches)


def _llm_reflection_to_reflection(llm: _LLMReflection) -> Reflection:
    return Reflection(
        error_signature=llm.error_signature,
        root_cause=llm.root_cause,
        normalized_error_text=llm.normalized_error_text,
        fix_plan=_llm_plan_to_plan(llm.fix_plan),
    )


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class ModelProvider(ABC):
    """Abstract interface for plan / reflection generation."""

    @abstractmethod
    def generate_initial_plan(self, task: TaskConfig, workspace_root: Path | None = None) -> Plan:
        """Produce the initial plan for iteration 0."""

    @abstractmethod
    def reflect_and_propose(
        self,
        task: TaskConfig,
        test_result: TestResult,
        history: List[Reflection],
        workspace_root: Path,
    ) -> Reflection:
        """Given the latest test result and prior reflections, produce a structured reflection."""


# ---------------------------------------------------------------------------
# Heuristic (offline) provider
# ---------------------------------------------------------------------------

class HeuristicModelProvider(ModelProvider):
    """Deterministic, offline model provider built from hand-written heuristics."""

    def generate_initial_plan(self, task: TaskConfig, workspace_root: Path | None = None) -> Plan:
        return Plan(description=f"Initial test run for goal: {task.goal}", patches=[])

    def reflect_and_propose(
        self,
        task: TaskConfig,
        test_result: TestResult,
        history: List[Reflection],
        workspace_root: Path,
    ) -> Reflection:
        return heuristic_reflect(test_result, workspace_root)


# ---------------------------------------------------------------------------
# OpenAI LLM provider
# ---------------------------------------------------------------------------

class OpenAIModelProvider(ModelProvider):
    """LLM-backed provider using OpenAI structured outputs."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def generate_initial_plan(self, task: TaskConfig, workspace_root: Path | None = None) -> Plan:
        if workspace_root is None:
            # Workspace not yet available — just run tests to discover failures.
            return Plan(description=f"Initial test run for goal: {task.goal}", patches=[])

        files = _collect_files(workspace_root)
        files_text = _format_files(files)

        prompt = (
            f"You are an expert Python software engineer.\n"
            f"Task goal: {task.goal}\n\n"
            f"Current source files:\n{files_text}\n\n"
            f"Analyse the code and tests carefully. Identify all bugs and missing implementations "
            f"then propose a complete fix. Return the full new content for every file you modify. "
            f"If no changes are needed, return an empty patches list."
        )

        try:
            response = self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format=_LLMPlan,
            )
            llm_plan = response.choices[0].message.parsed
            return _llm_plan_to_plan(llm_plan)
        except Exception:
            # Graceful fallback: let the test run reveal failures naturally.
            return Plan(description=f"Initial test run for goal: {task.goal}", patches=[])

    def reflect_and_propose(
        self,
        task: TaskConfig,
        test_result: TestResult,
        history: List[Reflection],
        workspace_root: Path,
    ) -> Reflection:
        files = _collect_files(workspace_root)
        files_text = _format_files(files)
        test_output = (test_result.stdout + "\n" + test_result.stderr).strip()

        history_text = ""
        if history:
            entries = []
            for i, r in enumerate(history, 1):
                entries.append(f"Attempt {i}: {r.root_cause}")
            history_text = "\n".join(entries)
        else:
            history_text = "None"

        prompt = (
            f"You are an expert Python software engineer debugging failing pytest output.\n"
            f"Task goal: {task.goal}\n\n"
            f"Current source files:\n{files_text}\n\n"
            f"Test failure output:\n{test_output}\n\n"
            f"Previous fix attempts:\n{history_text}\n\n"
            f"Analyse the failures carefully. Identify the root cause and propose a concrete fix. "
            f"Return the complete new content for every file you modify. "
            f"The error_signature must be a short snake_case identifier that is stable for this "
            f"specific error type (e.g. 'insufficient_funds_no_overdraft'). "
            f"normalized_error_text should be the key error line(s) from the test output."
        )

        try:
            response = self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format=_LLMReflection,
            )
            llm_reflection = response.choices[0].message.parsed
            return _llm_reflection_to_reflection(llm_reflection)
        except Exception:
            # Graceful fallback to heuristic.
            return heuristic_reflect(test_result, workspace_root)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_model_provider() -> ModelProvider:
    """Select provider based on environment variables. Defaults to heuristic."""
    provider_name = os.getenv("MODEL_PROVIDER", "heuristic").lower()
    api_key = os.getenv("OPENAI_API_KEY")

    if provider_name == "openai" and api_key:
        return OpenAIModelProvider(api_key=api_key)

    return HeuristicModelProvider()
