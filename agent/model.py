from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import List

from .reflection import reflect as heuristic_reflect
from .schemas import Plan, Reflection, TaskConfig, TestResult


class ModelProvider(ABC):
    """
    Abstract interface for plan / reflection generation.

    The rest of the agent should depend on this interface rather than on any
    particular LLM or heuristic implementation.
    """

    @abstractmethod
    def generate_initial_plan(self, task: TaskConfig) -> Plan:
        """Produce the initial plan for iteration 0."""

    @abstractmethod
    def reflect_and_propose(
        self,
        task: TaskConfig,
        test_result: TestResult,
        history: List[Reflection],
        workspace_root,
    ) -> Reflection:
        """
        Given the latest test result and prior reflections, produce a new
        structured reflection including a concrete fix plan.
        """


class HeuristicModelProvider(ModelProvider):
    """
    Deterministic, offline model provider built from hand-written heuristics.
    """

    def generate_initial_plan(self, task: TaskConfig) -> Plan:
        return Plan(description=f"Initial test run for goal: {task.goal}", patches=[])

    def reflect_and_propose(
        self,
        task: TaskConfig,
        test_result: TestResult,
        history: List[Reflection],
        workspace_root,
    ) -> Reflection:
        return heuristic_reflect(test_result, workspace_root)


class OpenAIModelProvider(ModelProvider):
    """
    Optional LLM-backed provider.

    This is intentionally a stub: it is only instantiated when the appropriate
    environment variables are set, and the project is expected to run entirely
    in heuristic mode by default.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def generate_initial_plan(self, task: TaskConfig) -> Plan:
        # Placeholder: real implementation would call an LLM.
        return Plan(description=f"Initial test run for goal: {task.goal}", patches=[])

    def reflect_and_propose(
        self,
        task: TaskConfig,
        test_result: TestResult,
        history: List[Reflection],
        workspace_root,
    ) -> Reflection:
        # Placeholder deterministic fallback to keep behavior predictable when
        # accidentally invoked.
        return heuristic_reflect(test_result, workspace_root)


def get_model_provider() -> ModelProvider:
    """
    Select an appropriate model provider based on environment variables.

    Defaults to the heuristic provider for deterministic offline operation.
    """
    provider_name = os.getenv("MODEL_PROVIDER", "heuristic").lower()
    api_key = os.getenv("OPENAI_API_KEY")

    if provider_name == "openai" and api_key:
        return OpenAIModelProvider(api_key=api_key)

    # Fallback: always heuristic.
    return HeuristicModelProvider()

