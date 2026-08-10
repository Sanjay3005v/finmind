"""LangGraph agent orchestration layer (Phase 6).

Sub-modules:
  llm.py        - fallback-chained chat model factory (OpenAI -> Groq -> Gemini)
  state.py      - AgentState graph state schema
  tools.py      - per-request LangChain tool factory, wraps app/financial + app/rag
  graph.py      - StateGraph definition (router, portfolio/research/risk/trade/
                   general nodes, self-reflection critic, trade interrupt)
  checkpoint.py - Postgres/Memory checkpointer lifecycle + DSN conversion
"""
