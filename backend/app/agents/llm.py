"""LLM provider fallback chain: OpenAI (primary) -> Groq -> Gemini.

Hard rule (docs/ARCHITECTURE.md section 5): graph nodes must never depend on
a specific provider SDK — every chat/structured-output call goes through one
of the factories below, which returns a single `Runnable` that internally
retries against the next provider in the chain on failure via LangChain's
real `.with_fallbacks()`.

Composition note: `.with_fallbacks()` is a generic `Runnable` method, but
`.with_structured_output(schema)` and `.bind_tools(tools)` are
`BaseChatModel`-specific methods that only exist on the raw chat model, not
on the `RunnableWithFallbacks` wrapper `.with_fallbacks()` returns. So the
per-provider transform (structured output / tool binding) MUST be applied to
each provider individually, BEFORE composing the fallback chain — not after.
Empirically this composes cleanly (see the throwaway smoke test run during
Phase 6 verification): `provider.with_structured_output(schema)` for each of
OpenAI/Groq/Gemini, then `openai_structured.with_fallbacks([groq_structured,
gemini_structured])`, works end-to-end with real OpenAI. No hand-rolled
try/except cascade was needed.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.core.errors import AppError

T = TypeVar("T")

_REQUEST_TIMEOUT_SECONDS = 30.0


def _build_providers(temperature: float = 0.0) -> list[BaseChatModel]:
    """Returns the configured providers in priority order: OpenAI, then
    Groq, then Gemini. A provider is included only if its API key is set —
    an unconfigured provider is skipped rather than constructed with an
    empty key (which would fail confusingly at call time instead of being
    cleanly absent from the chain)."""
    settings = get_settings()
    providers: list[BaseChatModel] = []

    if settings.OPENAI_API_KEY:
        providers.append(
            ChatOpenAI(
                model=settings.OPENAI_MODEL or "gpt-4.1-mini",
                temperature=temperature,
                api_key=settings.OPENAI_API_KEY,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        )
    if settings.GROQ_API_KEY:
        providers.append(
            ChatGroq(
                model=settings.GROQ_MODEL or "llama-3.3-70b-versatile",
                temperature=temperature,
                api_key=settings.GROQ_API_KEY,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        )
    if settings.GEMINI_API_KEY:
        # Structurally always included so the fallback chain has three links
        # end-to-end, per Phase 6 spec — even though the currently-configured
        # key returns HTTP 429 (zero quota) in practice, so it only ever
        # matters once a real quota is attached.
        providers.append(
            ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL or "gemini-2.0-flash",
                temperature=temperature,
                api_key=settings.GEMINI_API_KEY,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        )

    if not providers:
        raise AppError(
            code="LLM_UNAVAILABLE",
            message="No LLM provider API key is configured (OPENAI_API_KEY/GROQ_API_KEY/GEMINI_API_KEY).",
            status_code=500,
        )
    return providers


def _compose_with_fallbacks(
    providers: Sequence[BaseChatModel], transform: Optional[Callable[[BaseChatModel], Runnable]] = None
) -> Runnable:
    chain = [transform(p) if transform else p for p in providers]
    primary, *fallbacks = chain
    if not fallbacks:
        return primary
    return primary.with_fallbacks(fallbacks)


def get_chat_model(temperature: float = 0.0) -> Runnable:
    """Plain chat model: OpenAI primary, falls back to Groq then Gemini on
    any error (rate limit, timeout, auth failure, etc.). Callers that need
    tool-calling should use `get_tool_calling_model` instead — `bind_tools`
    must be applied per-provider before the fallback chain is composed."""
    return _compose_with_fallbacks(_build_providers(temperature))


def get_tool_calling_model(tools: Sequence, temperature: float = 0.0) -> Runnable:
    """Chat model with `tools` bound on every provider individually, then
    composed into the same OpenAI -> Groq -> Gemini fallback chain."""
    return _compose_with_fallbacks(_build_providers(temperature), transform=lambda m: m.bind_tools(tools))


def get_structured_model(schema: type, temperature: float = 0.0) -> Runnable:
    """Structured-output model (e.g. router intent classification): each
    provider gets `.with_structured_output(schema)` applied individually,
    then the three structured-output runnables are composed into the
    fallback chain. Verified empirically against real OpenAI during Phase 6
    verification — see module docstring."""
    return _compose_with_fallbacks(
        _build_providers(temperature), transform=lambda m: m.with_structured_output(schema)
    )
