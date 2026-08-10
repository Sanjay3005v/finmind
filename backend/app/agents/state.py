"""Graph state schema for the FINMIND agent (docs/ARCHITECTURE.md section 5).

A `TypedDict` (not a Pydantic model) because LangGraph's `StateGraph` reducer
mechanism (`Annotated[list, add_messages]`) is designed around TypedDict/
dataclass state — Pydantic models work too but add validation overhead on
every node transition for no benefit here, since every field is already
produced by trusted internal code, never raw user input.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

Intent = Literal["portfolio", "research", "risk", "trade", "general"]


class ToolResult(TypedDict):
    name: str
    args: dict
    result: Any


class CitationDict(TypedDict):
    marker: int
    document_id: str
    document_title: str
    chunk_id: str
    chunk_index: int
    snippet: str


class AgentState(TypedDict, total=False):
    # Conversation transcript for this thread (LangChain message objects);
    # `add_messages` appends/merges by message id rather than overwriting.
    messages: Annotated[list[BaseMessage], add_messages]

    # Request scoping (set once per turn, never mutated by nodes).
    session_id: str
    user_id: str
    portfolio_id: Optional[str]

    # Router output.
    intent: Optional[Intent]

    # Every tool call made THIS turn, in call order — the self-reflection
    # critic cross-references every numeric claim in `draft_answer` against
    # this list (rule #1: the LLM never computes financial numbers itself).
    tool_results: list[ToolResult]

    # Synthesis output, re-written on each self-reflection retry.
    draft_answer: str
    citations: list[CitationDict]

    # Self-reflection loop control.
    reflection_attempts: int
    reflection_feedback: Optional[str]
    reflection_passed: bool

    # Trade proposal / human-in-the-loop.
    pending_trade_approval_id: Optional[str]
    trade_proposal: Optional[dict]
