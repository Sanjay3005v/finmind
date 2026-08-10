"""Shared fakes for agent tests — NOT collected by pytest (filename doesn't
match `test_*.py`). Mocks `app.agents.graph.get_chat_model` /
`get_structured_model` so graph tests never call a real LLM provider or
spend API credits, exactly the pattern `tests/test_research_api.py` already
uses for `research_service._synthesize`.
"""
from __future__ import annotations

from typing import Any, Optional

import app.agents.graph as graph_mod


class FakeAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeRunnable:
    def __init__(self, fn) -> None:
        self._fn = fn

    async def ainvoke(self, messages: Any):
        return await self._fn(messages)


def fake_chat_model(answer_text: str):
    """Drop-in replacement for `app.agents.llm.get_chat_model` — always
    returns `answer_text` regardless of the prompt it's given."""

    async def _respond(_messages):
        return FakeAIMessage(answer_text)

    def _factory(temperature: float = 0.0):
        return FakeRunnable(_respond)

    return _factory


def fake_structured_model(
    router_intent: Optional[str] = None,
    trade_proposal: Any = None,
    reflection_verdict: Any = None,
):
    """Drop-in replacement for `app.agents.llm.get_structured_model` —
    dispatches on the Pydantic schema class each call site asks for."""

    def _factory(schema: type, temperature: float = 0.0):
        async def _respond(_messages):
            if schema is graph_mod.RouterDecision:
                return graph_mod.RouterDecision(intent=router_intent or "general")
            if schema is graph_mod.TradeProposal:
                if trade_proposal is None:
                    raise AssertionError("fake_structured_model: no trade_proposal configured")
                return trade_proposal
            if schema is graph_mod.ReflectionVerdict:
                return reflection_verdict or graph_mod.ReflectionVerdict(passed=True, reasons="ok")
            raise AssertionError(f"fake_structured_model: unexpected schema {schema}")

        return FakeRunnable(_respond)

    return _factory
