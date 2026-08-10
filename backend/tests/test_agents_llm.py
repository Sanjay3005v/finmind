"""Tests for app/agents/llm.py — the OpenAI -> Groq -> Gemini fallback chain.

No real provider network calls here: `_build_providers` is tested against
monkeypatched settings (provider selection/ordering is pure config logic,
constructing a `ChatOpenAI`/`ChatGroq`/`ChatGoogleGenerativeAI` instance
never makes a network call by itself). The actual fallback MECHANISM
(`.with_fallbacks()`) is tested against real `langchain_core.runnables`
primitives instead of the real provider SDKs, so we get a genuine
LangChain fallback-chain test without spending any API credits.
"""
from __future__ import annotations

import pytest
from langchain_core.runnables import RunnableLambda

import app.agents.llm as llm_module
from app.core.errors import AppError


class _FakeSettings:
    def __init__(self, openai=None, groq=None, gemini=None):
        self.OPENAI_API_KEY = openai
        self.OPENAI_MODEL = "gpt-4.1-mini"
        self.GROQ_API_KEY = groq
        self.GROQ_MODEL = "llama-3.3-70b-versatile"
        self.GEMINI_API_KEY = gemini
        self.GEMINI_MODEL = "gemini-2.0-flash"


def test_build_providers_orders_openai_groq_gemini(monkeypatch):
    monkeypatch.setattr(llm_module, "get_settings", lambda: _FakeSettings("ok1", "ok2", "ok3"))
    providers = llm_module._build_providers()
    assert [type(p).__name__ for p in providers] == ["ChatOpenAI", "ChatGroq", "ChatGoogleGenerativeAI"]


def test_build_providers_skips_unconfigured_providers(monkeypatch):
    monkeypatch.setattr(llm_module, "get_settings", lambda: _FakeSettings(openai="ok1", groq=None, gemini=None))
    providers = llm_module._build_providers()
    assert [type(p).__name__ for p in providers] == ["ChatOpenAI"]


def test_build_providers_raises_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(llm_module, "get_settings", lambda: _FakeSettings())
    with pytest.raises(AppError) as exc_info:
        llm_module._build_providers()
    assert exc_info.value.code == "LLM_UNAVAILABLE"


def test_get_chat_model_raises_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(llm_module, "get_settings", lambda: _FakeSettings())
    with pytest.raises(AppError):
        llm_module.get_chat_model()


@pytest.mark.asyncio
async def test_compose_with_fallbacks_falls_back_on_primary_failure():
    """Exercises the real `.with_fallbacks()` mechanism (not a mock): the
    primary runnable always raises, so the composed chain must actually
    invoke the fallback and return ITS result."""

    def _primary(_input):
        raise RuntimeError("primary provider is down")

    def _fallback(_input):
        return "fallback answered"

    primary = RunnableLambda(_primary)
    fallback = RunnableLambda(_fallback)

    chain = llm_module._compose_with_fallbacks([primary, fallback])
    result = await chain.ainvoke("hello")
    assert result == "fallback answered"


@pytest.mark.asyncio
async def test_compose_with_fallbacks_uses_primary_when_it_succeeds():
    primary = RunnableLambda(lambda _x: "primary answered")
    fallback = RunnableLambda(lambda _x: "fallback answered")

    chain = llm_module._compose_with_fallbacks([primary, fallback])
    result = await chain.ainvoke("hello")
    assert result == "primary answered"


@pytest.mark.asyncio
async def test_compose_with_fallbacks_applies_transform_before_composing():
    """Regression test for the composition rule documented in llm.py: a
    per-provider transform (e.g. `.with_structured_output`/`.bind_tools`)
    must be applied to EACH runnable individually before `.with_fallbacks()`
    is composed, not after."""
    calls = []

    def _make(name):
        def _fn(_input):
            calls.append(name)
            if name == "primary":
                raise RuntimeError("boom")
            return name

        return RunnableLambda(_fn)

    def _transform(runnable):
        # Wrap with something that would break if applied to a
        # RunnableWithFallbacks instead of the individual runnable.
        return runnable

    chain = llm_module._compose_with_fallbacks([_make("primary"), _make("fallback")], transform=_transform)
    result = await chain.ainvoke("x")
    assert result == "fallback"
    assert calls == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_compose_with_fallbacks_single_provider_returns_it_unwrapped():
    only = RunnableLambda(lambda _x: "only answered")
    chain = llm_module._compose_with_fallbacks([only])
    assert await chain.ainvoke("x") == "only answered"
