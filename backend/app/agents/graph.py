"""FINMIND agent StateGraph (docs/ARCHITECTURE.md section 5).

    route -> {portfolio|research|risk|general} -> self_reflection -> loop or END
    route -> trade_propose -> trade_interrupt -> END   (never touches self_reflection)

Design notes / deliberate choices:

- **Deterministic tool invocation, not LLM tool-choice.** `portfolio_node`
  and `risk_node` call their tools directly (not via `bind_tools` + a
  tool-execution loop). This guarantees rule #1 ("the LLM never computes
  financial numbers") structurally — the numbers exist in `tool_results`
  BEFORE the LLM is ever invoked to narrate them, rather than hoping the LLM
  chooses to call the right tool before answering. `research_node` follows
  the same shape for the same reason. Tools are still built as real
  LangChain `@tool` objects via `app/agents/tools.py::build_tools` (so they
  carry the precise docstrings the spec asks for, and could be handed to
  `get_tool_calling_model` later if a fully agentic loop is ever wanted) —
  they're just invoked directly here via `.ainvoke(args)`.

- **Self-reflection's numeric/citation check is deterministic, not
  LLM-judged.** A hard invariant ("force a regeneration if a number doesn't
  match anything a tool returned") must not depend on an LLM's mood. The
  node cross-references every numeric literal in the draft against every
  numeric leaf value in this turn's `tool_results` (rule #1) or every `[n]`
  citation marker against the citations that were actually extracted via
  `research_service._extract_citations` (rule #3) — both in plain Python.
  A critic LLM call still runs (per the Phase 6 spec: "via one more LLM
  call scoring pass/fail + reasons") to catch softer issues and produce a
  human-readable `reasons` string, but it can only ever tighten a pass into
  a fail, never launder a deterministic fail into a pass.

- **Trade proposals never re-execute side effects on resume.** `interrupt()`
  causes LangGraph to re-run the *current* node from the top when the graph
  is resumed, so any node that calls `interrupt()` must not have side
  effects before that call — otherwise resuming a trade would insert a
  second `trade_approvals` row. That's why trade handling is split into two
  nodes: `trade_propose` (creates the DB row, runs exactly once) and
  `trade_interrupt` (only calls `interrupt()` and narrates the outcome —
  safe to re-run).
"""
from __future__ import annotations

import json
import re
from typing import Literal, Optional
from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.agents.llm import get_chat_model, get_structured_model
from app.agents.state import AgentState
from app.agents.tools import AgentToolError
from app.models.trade_approval import TradeApproval
from app.rag.retrieval import RetrievedChunk
from app.services.research_service import _extract_citations

logger = structlog.get_logger(__name__)

MAX_REFLECTION_RETRIES = 2  # total regenerations allowed after the first draft


# ─────────────────────────────────────────────────────────────────────────
# Structured-output schemas
# ─────────────────────────────────────────────────────────────────────────
class RouterDecision(BaseModel):
    intent: Literal["portfolio", "research", "risk", "trade", "general"] = Field(
        description=(
            "portfolio: holdings/performance questions. research: questions about "
            "documents/filings/market research. risk: volatility/drawdown/"
            "concentration/diversification questions. trade: the user wants to "
            "buy/sell/place an order. general: small talk or a clarifying question."
        )
    )


class TradeProposal(BaseModel):
    symbol: str = Field(description="Ticker symbol the user wants to trade, e.g. RELIANCE.")
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    order_type: Literal["market", "limit"] = "market"
    limit_price: Optional[float] = Field(default=None, description="Required only if order_type is 'limit'.")
    reasoning: str = Field(description="One or two sentences explaining why this trade is being proposed.")


class ReflectionVerdict(BaseModel):
    passed: bool = Field(description="True only if every claim in the draft is actually supported by the evidence.")
    reasons: str = Field(description="Short explanation of the verdict; if failed, what specifically to fix.")


# ─────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────
def _get_tools(config: RunnableConfig) -> dict:
    return (config.get("configurable") or {}).get("tools", {})


def _get_db(config: RunnableConfig):
    return (config.get("configurable") or {}).get("db")


def _last_human_text(state: AgentState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def _infer_range(text: str) -> str:
    lowered = text.lower()
    if "3 month" in lowered or "3m" in lowered or "quarter" in lowered:
        return "3M"
    if "1 month" in lowered or "1m" in lowered or "this month" in lowered:
        return "1M"
    if "1 year" in lowered or "1y" in lowered or "annual" in lowered or "ytd" in lowered:
        return "1Y"
    return "ALL"


async def _narrate(system_prompt: str, user_text: str, tool_results: list[dict], feedback: Optional[str]) -> str:
    payload = json.dumps(
        [{"name": t["name"], "args": t.get("args", {}), "result": t["result"]} for t in tool_results], default=str
    )
    messages = [
        SystemMessage(system_prompt),
        HumanMessage(f"User question: {user_text}\n\nTool results (JSON, the ONLY source of numbers you may use):\n{payload}"),
    ]
    if feedback:
        messages.append(
            HumanMessage(
                f"A previous draft failed review for this reason: {feedback}\n"
                "Regenerate the answer, fixing this issue, using ONLY the numbers in the tool results above."
            )
        )
    model = get_chat_model()
    response = await model.ainvoke(messages)
    return response.content if isinstance(response.content, str) else str(response.content)


# ─────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────
_ROUTER_SYSTEM_PROMPT = (
    "You are the intent router for FINMIND, an investment research and portfolio "
    "analyst assistant. Classify the user's latest message into exactly one intent."
)


async def route_node(state: AgentState, config: RunnableConfig) -> dict:
    user_text = _last_human_text(state)
    model = get_structured_model(RouterDecision)
    try:
        decision = await model.ainvoke([SystemMessage(_ROUTER_SYSTEM_PROMPT), HumanMessage(user_text)])
    except Exception as exc:  # noqa: BLE001 — never crash the graph on a router hiccup
        logger.warning("router_classification_failed", error=str(exc))
        return {"intent": "general"}
    return {"intent": decision.intent, "reflection_attempts": 0, "reflection_feedback": None}


def route_decision(state: AgentState) -> str:
    return state.get("intent") or "general"


# ─────────────────────────────────────────────────────────────────────────
# Portfolio agent
# ─────────────────────────────────────────────────────────────────────────
_PORTFOLIO_SYSTEM_PROMPT = (
    "You are FINMIND's portfolio analyst. Narrate the user's holdings and performance "
    "using ONLY the numbers in the tool results you are given — never estimate, round "
    "creatively, or state a number that isn't present in the tool results. If a metric "
    "is null, say it isn't available rather than guessing."
)


async def portfolio_node(state: AgentState, config: RunnableConfig) -> dict:
    tools = _get_tools(config)
    user_text = _last_human_text(state)
    feedback = state.get("reflection_feedback")

    tool_results: list[dict] = []
    try:
        holdings_result = await tools["get_holdings_summary"].ainvoke({})
        tool_results.append({"name": "get_holdings_summary", "args": {}, "result": holdings_result})
        perf_range = _infer_range(user_text)
        perf_result = await tools["compute_performance"].ainvoke({"range": perf_range})
        tool_results.append({"name": "compute_performance", "args": {"range": perf_range}, "result": perf_result})
    except AgentToolError as exc:
        return {
            "tool_results": [{"name": "portfolio_tools", "args": {}, "result": {"error": str(exc)}}],
            "draft_answer": f"I couldn't retrieve your portfolio data: {exc}",
            "citations": [],
        }

    draft = await _narrate(_PORTFOLIO_SYSTEM_PROMPT, user_text, tool_results, feedback)
    return {"tool_results": tool_results, "draft_answer": draft, "citations": []}


# ─────────────────────────────────────────────────────────────────────────
# Risk agent
# ─────────────────────────────────────────────────────────────────────────
_RISK_SYSTEM_PROMPT = (
    "You are FINMIND's risk analyst. Narrate the user's risk profile (volatility, "
    "Sharpe/Sortino ratios, max drawdown, concentration) and allocation breakdown "
    "using ONLY the numbers in the tool results you are given — never estimate a "
    "number that isn't present in the tool results. If beta is unavailable, say so."
)


async def risk_node(state: AgentState, config: RunnableConfig) -> dict:
    tools = _get_tools(config)
    user_text = _last_human_text(state)
    feedback = state.get("reflection_feedback")

    tool_results: list[dict] = []
    try:
        risk_result = await tools["compute_risk_metrics"].ainvoke({})
        tool_results.append({"name": "compute_risk_metrics", "args": {}, "result": risk_result})
        allocation_result = await tools["compute_allocation_breakdown"].ainvoke({})
        tool_results.append({"name": "compute_allocation_breakdown", "args": {}, "result": allocation_result})
    except AgentToolError as exc:
        return {
            "tool_results": [{"name": "risk_tools", "args": {}, "result": {"error": str(exc)}}],
            "draft_answer": f"I couldn't compute your risk metrics: {exc}",
            "citations": [],
        }

    draft = await _narrate(_RISK_SYSTEM_PROMPT, user_text, tool_results, feedback)
    return {"tool_results": tool_results, "draft_answer": draft, "citations": []}


# ─────────────────────────────────────────────────────────────────────────
# Research agent
# ─────────────────────────────────────────────────────────────────────────
_RESEARCH_SYSTEM_PROMPT = (
    "You are FINMIND's research assistant. Answer the user's question using ONLY the "
    "numbered source passages provided below — never use outside knowledge. Cite the "
    "source of every factual claim with its bracketed number, e.g. [1], immediately "
    "after the claim. If the provided passages do not contain enough information, say "
    "so explicitly rather than guessing."
)


async def research_node(state: AgentState, config: RunnableConfig) -> dict:
    tools = _get_tools(config)
    user_text = _last_human_text(state)
    feedback = state.get("reflection_feedback")

    try:
        result = await tools["research_lookup"].ainvoke({"query": user_text})
    except AgentToolError as exc:
        return {
            "tool_results": [{"name": "research_lookup", "args": {"query": user_text}, "result": {"error": str(exc)}}],
            "draft_answer": f"I couldn't search the research library: {exc}",
            "citations": [],
        }

    tool_results = [{"name": "research_lookup", "args": {"query": user_text}, "result": result}]
    chunks_data = result.get("chunks", [])
    if not chunks_data:
        return {
            "tool_results": tool_results,
            "draft_answer": "I couldn't find any documents in your research library that address this question.",
            "citations": [],
        }

    context = "\n\n".join(f"[{i + 1}] (source: {c['document_title']})\n{c['content']}" for i, c in enumerate(chunks_data))
    messages = [_system(_RESEARCH_SYSTEM_PROMPT), HumanMessage(f"Sources:\n{context}\n\nQuestion: {user_text}")]
    if feedback:
        messages.append(
            HumanMessage(
                f"A previous draft failed review for this reason: {feedback}\n"
                "Regenerate, citing ONLY the numbered sources above and never a source number that doesn't exist."
            )
        )
    model = get_chat_model()
    response = await model.ainvoke(messages)
    answer = response.content if isinstance(response.content, str) else str(response.content)

    # Reuse the exact citation-safety pattern proven in research_service —
    # only keep [n] markers that both appear in the model output AND map to
    # an actually-retrieved chunk (rule #3).
    chunk_objs = [
        RetrievedChunk(
            chunk_id=c["chunk_id"],
            document_id=c["document_id"],
            document_title=c["document_title"],
            chunk_index=c["chunk_index"],
            content=c["content"],
            score=0.0,
        )
        for c in chunks_data
    ]
    citations = _extract_citations(answer, chunk_objs)
    citation_dicts = [
        {
            "marker": c.marker,
            "document_id": c.document_id,
            "document_title": c.document_title,
            "chunk_id": c.chunk_id,
            "chunk_index": c.chunk_index,
            "snippet": c.snippet,
        }
        for c in citations
    ]
    return {"tool_results": tool_results, "draft_answer": answer, "citations": citation_dicts}


def _system(text: str) -> SystemMessage:
    return SystemMessage(text)


# ─────────────────────────────────────────────────────────────────────────
# General (small talk / clarifying questions) — no tools
# ─────────────────────────────────────────────────────────────────────────
_GENERAL_SYSTEM_PROMPT = (
    "You are FINMIND's assistant. Answer small talk or ask a clarifying question about "
    "the user's portfolio/research/risk/trade needs. Never state a specific financial "
    "number (return, price, ratio, percentage) in this mode — you have no tool results "
    "to ground one; if the user wants a number, ask them to specify what they want "
    "looked up instead."
)


async def general_node(state: AgentState, config: RunnableConfig) -> dict:
    user_text = _last_human_text(state)
    model = get_chat_model()
    response = await model.ainvoke([SystemMessage(_GENERAL_SYSTEM_PROMPT), HumanMessage(user_text)])
    answer = response.content if isinstance(response.content, str) else str(response.content)
    return {"tool_results": [], "draft_answer": answer, "citations": []}


# ─────────────────────────────────────────────────────────────────────────
# Trade proposal + human-in-the-loop interrupt (rule #2)
# ─────────────────────────────────────────────────────────────────────────
async def trade_propose_node(state: AgentState, config: RunnableConfig) -> dict:
    """Creates the `trade_approvals` row (status='pending'). Runs exactly
    once per turn — never call a broker here, and never put anything with a
    side effect after this node other than `trade_interrupt_node`'s
    `interrupt()` call itself."""
    db = _get_db(config)
    user_text = _last_human_text(state)

    extractor = get_structured_model(TradeProposal)
    try:
        proposal = await extractor.ainvoke(
            [
                SystemMessage(
                    "Extract the trade the user wants to propose from their message. "
                    "If order_type is 'limit', extract limit_price too."
                ),
                HumanMessage(user_text),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("trade_extraction_failed", error=str(exc))
        return {
            "draft_answer": "I couldn't understand the trade you want to make — could you restate the symbol, side, and quantity?",
            "tool_results": [],
            "citations": [],
        }

    approval = TradeApproval(
        session_id=UUID(state["session_id"]) if state.get("session_id") else None,
        user_id=UUID(state["user_id"]),
        symbol=proposal.symbol.upper(),
        side=proposal.side,
        quantity=proposal.quantity,
        order_type=proposal.order_type,
        limit_price=proposal.limit_price,
        status="pending",
        requested_by="agent",
        reasoning=proposal.reasoning,
    )
    db.add(approval)
    await db.flush()
    await db.refresh(approval)

    return {
        "pending_trade_approval_id": str(approval.id),
        "trade_proposal": {
            "trade_approval_id": str(approval.id),
            "symbol": approval.symbol,
            "side": approval.side,
            "quantity": float(approval.quantity),
            "order_type": approval.order_type,
            "limit_price": float(approval.limit_price) if approval.limit_price is not None else None,
        },
    }


async def trade_interrupt_node(state: AgentState, config: RunnableConfig) -> dict:
    """The ONLY node allowed to call `interrupt()`. Has no DB side effects
    of its own, so re-running it on resume (LangGraph's replay semantics)
    is always safe."""
    proposal = state.get("trade_proposal") or {}
    decision = interrupt(proposal)
    return {"draft_answer": _render_trade_ack(decision), "tool_results": [], "citations": []}


def _render_trade_ack(decision) -> str:
    if not isinstance(decision, dict):
        return "Your trade proposal has been reviewed."
    status = decision.get("status", "unknown")
    symbol = decision.get("symbol", "")
    side = decision.get("side", "")
    quantity = decision.get("quantity", "")
    if status == "executed":
        order_id = decision.get("broker_order_id", "n/a")
        return (
            f"Your {side} order for {quantity} {symbol} was approved and executed in paper "
            f"trading mode (order id {order_id}). No live order was ever placed."
        )
    if status == "rejected":
        note = decision.get("note")
        suffix = f" Note from you: {note}" if note else ""
        return f"Understood — the proposed {side} order for {quantity} {symbol} was not approved.{suffix}"
    if status == "failed":
        return f"The approved {side} order for {quantity} {symbol} could not be executed: {decision.get('note', 'unknown error')}."
    return f"The trade proposal for {quantity} {symbol} is now '{status}'."


# ─────────────────────────────────────────────────────────────────────────
# Self-reflection critic (rules #1 and #3)
# ─────────────────────────────────────────────────────────────────────────
_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*%?")


def _strip_citation_markers(text: str) -> str:
    return re.sub(r"\[\d+\]", " ", text)


def _flatten_numbers(obj) -> set[float]:
    numbers: set[float] = set()
    if isinstance(obj, bool):
        return numbers
    if isinstance(obj, (int, float)):
        numbers.add(round(float(obj), 4))
    elif isinstance(obj, dict):
        for v in obj.values():
            numbers |= _flatten_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            numbers |= _flatten_numbers(v)
    return numbers


def _extract_claimed_numbers(text: str) -> list[tuple[float, bool]]:
    """Returns `(value, is_percentage)` pairs — `is_percentage` is only True
    when the literal token was followed by `%` in the text, so the fraction
    vs. percent-display equivalence (rule #1's tolerance) is only applied
    where the text actually signals a percentage, not to every number
    (a blanket /100 fallback is too permissive — see the regression test
    for the exact false-positive it caused: a plainly fabricated number
    could coincidentally land within tolerance of an unrelated reference
    value once divided by 100)."""
    stripped = _strip_citation_markers(text)
    values: list[tuple[float, bool]] = []
    for raw in _NUMBER_RE.findall(stripped):
        is_pct = raw.endswith("%")
        cleaned = raw[:-1] if is_pct else raw
        cleaned = cleaned.replace(",", "")
        if cleaned in ("", "-", "."):
            continue
        try:
            val = float(cleaned)
        except ValueError:
            continue
        if not is_pct and val == int(val) and 2000 <= val <= 2099:
            continue  # looks like a calendar year, not a financial figure
        values.append((val, is_pct))
    return values


def _numeric_claims_unmatched(draft: str, tool_results: list[dict], tolerance: float = 0.02) -> list[float]:
    """Every number in `draft` must be traceable to some numeric value a
    tool actually returned this turn (allowing for percent vs. fraction
    display, only when the text marks it with `%`, and small rounding) —
    rule #1."""
    reference: set[float] = set()
    for tr in tool_results:
        reference |= _flatten_numbers(tr.get("result"))
    if not reference:
        return []
    unmatched: list[float] = []
    for claimed, is_pct in _extract_claimed_numbers(draft):
        candidates = {claimed, claimed / 100.0} if is_pct else {claimed}
        if any(abs(c - r) <= max(tolerance, abs(r) * tolerance) for c in candidates for r in reference):
            continue
        unmatched.append(claimed)
    return unmatched


def _invalid_citation_markers(draft: str, citations: list[dict]) -> list[int]:
    """Every `[n]` marker in `draft` must be one that `_extract_citations`
    actually kept (i.e. mapped to a retrieved chunk) — rule #3."""
    markers_in_text = {int(m) for m in re.findall(r"\[(\d+)\]", draft)}
    valid = {c["marker"] for c in citations}
    return sorted(markers_in_text - valid)


async def self_reflection_node(state: AgentState, config: RunnableConfig) -> dict:
    intent = state.get("intent", "general")
    draft = state.get("draft_answer", "")
    tool_results = state.get("tool_results", [])
    citations = state.get("citations", [])
    attempts = state.get("reflection_attempts", 0)

    unmatched_numbers: list[float] = []
    invalid_markers: list[int] = []
    if intent in ("portfolio", "risk"):
        unmatched_numbers = _numeric_claims_unmatched(draft, tool_results)
    elif intent == "research":
        invalid_markers = _invalid_citation_markers(draft, citations)

    deterministic_passed = not unmatched_numbers and not invalid_markers
    passed = deterministic_passed
    reasons = "No fabricated numbers or invalid citations detected."
    if not deterministic_passed:
        parts = []
        if unmatched_numbers:
            parts.append(
                f"The draft states {unmatched_numbers} which do not match any number returned by a tool call this turn."
            )
        if invalid_markers:
            parts.append(f"The draft cites source marker(s) {invalid_markers} which were never actually retrieved.")
        reasons = " ".join(parts)

    if deterministic_passed:
        # A deterministic pass may still be softened into a fail by the critic
        # (unsupported claims, missing context) — but a deterministic FAIL can
        # never be laundered into a pass by the LLM. See module docstring.
        try:
            critic = get_structured_model(ReflectionVerdict)
            verdict = await critic.ainvoke(
                [
                    SystemMessage(
                        "You are a strict fact-checking critic for a financial assistant. Given a draft "
                        "answer and the tool results / citations it was based on, verify every claim is "
                        "actually supported by that evidence. Respond with your verdict."
                    ),
                    HumanMessage(
                        f"Draft answer:\n{draft}\n\nTool results:\n{json.dumps(tool_results, default=str)}\n\n"
                        f"Citations:\n{json.dumps(citations, default=str)}"
                    ),
                ]
            )
            passed = bool(verdict.passed)
            if not passed:
                reasons = verdict.reasons or reasons
        except Exception as exc:  # noqa: BLE001 — critic call is best-effort on top of the deterministic check
            logger.warning("self_reflection_critic_call_failed", error=str(exc))

    if passed:
        return {"reflection_passed": True, "reflection_feedback": None}

    if attempts >= MAX_REFLECTION_RETRIES:
        logger.warning(
            "self_reflection_giving_up_after_max_retries", intent=intent, attempts=attempts, reasons=reasons
        )
        return {"reflection_passed": True, "reflection_feedback": reasons}

    return {"reflection_passed": False, "reflection_attempts": attempts + 1, "reflection_feedback": reasons}


def reflection_router(state: AgentState) -> str:
    if state.get("reflection_passed"):
        return "end"
    return state.get("intent") or "general"


# ─────────────────────────────────────────────────────────────────────────
# Graph assembly
# ─────────────────────────────────────────────────────────────────────────
def build_graph(checkpointer) -> CompiledStateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("route", route_node)
    graph.add_node("portfolio", portfolio_node)
    graph.add_node("research", research_node)
    graph.add_node("risk", risk_node)
    graph.add_node("general", general_node)
    graph.add_node("trade_propose", trade_propose_node)
    graph.add_node("trade_interrupt", trade_interrupt_node)
    graph.add_node("self_reflection", self_reflection_node)

    graph.set_entry_point("route")
    graph.add_conditional_edges(
        "route",
        route_decision,
        {
            "portfolio": "portfolio",
            "research": "research",
            "risk": "risk",
            "trade": "trade_propose",
            "general": "general",
        },
    )

    graph.add_edge("portfolio", "self_reflection")
    graph.add_edge("research", "self_reflection")
    graph.add_edge("risk", "self_reflection")
    graph.add_edge("general", "self_reflection")

    graph.add_conditional_edges(
        "self_reflection",
        reflection_router,
        {
            "portfolio": "portfolio",
            "research": "research",
            "risk": "risk",
            "general": "general",
            "end": END,
        },
    )

    graph.add_edge("trade_propose", "trade_interrupt")
    graph.add_edge("trade_interrupt", END)

    return graph.compile(checkpointer=checkpointer)
