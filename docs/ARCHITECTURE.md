# FINMIND — System Architecture

## 1. Overview

FINMIND is an AI Investment Research & Portfolio Analyst. It connects to a user's
brokerage accounts (via pluggable adapters), maintains a portfolio ledger, runs
deterministic financial analytics, retrieves and cites research documents (RAG),
and orchestrates specialized LLM agents (LangGraph) that can *recommend* trades —
but never execute one without explicit human approval.

Two hard rules govern every phase of this build:

1. **The LLM never performs financial arithmetic.** All returns, risk, and
   valuation numbers come from deterministic Python functions
   (`backend/app/financial/*`), unit tested independently of any model. Agents
   call these as LangGraph tools and only narrate/interpret the results.
2. **No live order is ever placed without a human-approved `TradeApproval`
   record.** Agents can *propose* trades; execution is a separate, audited,
   user-confirmed step. Broker adapters default to `paper` mode until a user
   explicitly attaches live sandbox/production credentials.

## 2. High-level topology

```
┌─────────────────────┐        HTTPS/JSON, SSE          ┌──────────────────────────┐
│   Next.js frontend   │ ───────────────────────────────▶│      FastAPI backend      │
│  (App Router, RSC)   │◀─────────────────────────────── │  (modular service layers) │
└──────────┬───────────┘        Bearer: Supabase JWT      └────────────┬─────────────┘
           │                                                            │
           │ supabase-js (auth session,                                │ asyncpg / SQLAlchemy
           │ storage for uploads)                                      │ (service-role, RLS-aware)
           ▼                                                            ▼
┌──────────────────────┐                                   ┌──────────────────────────┐
│   Supabase Postgres    │◀──────── pgvector, RLS ─────────│   Redis (cache, rate      │
│  (auth.users + public) │                                  │  limit, Celery broker)    │
└──────────────────────┘                                   └──────────────────────────┘
                                                                          │
                                                              ┌───────────┴───────────┐
                                                              │   Celery worker(s)    │
                                                              │ (broker sync, doc     │
                                                              │  ingestion, reports)  │
                                                              └───────────────────────┘

Backend also calls out to:
  - LLM providers: OpenAI (primary) → Groq (fallback) → Gemini (fallback)
  - Broker APIs: DhanHQ / Angel One SmartAPI / Upstox / FYERS (via adapters)
```

## 3. Backend module layout (`backend/app`)

```
app/
  core/        settings (pydantic-settings), structured logging (structlog),
               security (JWT verification), rate limiting (redis-backed),
               error handlers, request-id middleware
  db/          async SQLAlchemy engine/session, base model, migrations (alembic)
  models/      ORM models mirroring docs/DATABASE_SCHEMA.sql
  schemas/     Pydantic request/response contracts (see API_CONTRACTS.md)
  api/v1/      routers: auth, portfolios, holdings, broker_connections,
               documents, research, agents, trade_approvals, reports
  services/    business logic orchestration, one service per domain
  financial/   deterministic calculation tools (returns, risk, allocation)
  brokers/     BrokerAdapter ABC + dhan.py / angelone.py / upstox.py / fyers.py
               + mock.py (paper trading) + registry.py (factory)
  rag/         ingestion, chunking, embeddings, hybrid retrieval, reranking
  agents/      LangGraph graph definition, nodes, tools, llm_router,
               checkpointing (Postgres-backed)
  workers/     Celery app + tasks (broker sync, document ingestion, reports)
tests/         pytest, mirrors app/ layout
alembic/       migration scripts
```

## 4. Authentication & authorization model

- **Identity provider:** Supabase Auth (email/password + OAuth providers).
  The frontend never talks to the backend for login/signup — it uses
  `@supabase/ssr` directly against Supabase.
- **Backend verification:** every API request carries `Authorization: Bearer
  <supabase_access_token>`. The backend verifies the JWT against the
  Supabase project's JWT secret (HS256) and extracts `sub` as `user_id`.
  Invalid/expired tokens → `401`.
- **Authorization:** Postgres Row Level Security (RLS) is the source of
  truth for row-level access (`user_id = auth.uid()` on every user-owned
  table). The backend additionally checks resource ownership in the service
  layer before mutating state (defense in depth) and uses the Supabase
  **service role key** only for server-side, privileged operations (broker
  credential encryption/decryption, background sync jobs) — this key is
  never sent to the frontend.
- **Trade execution authorization:** placing a *live* order requires (a) a
  `broker_connections.mode = 'live'` record, (b) a `trade_approvals` row in
  `status = 'approved'` decided by the authenticated user themselves, and
  (c) re-confirmation of the exact symbol/qty/price at execution time. Any
  mismatch aborts the order.

## 5. Agent architecture (LangGraph)

```
            ┌──────────┐
   input ──▶│  Router  │──intent classification (portfolio | research | risk | trade | general)
            └────┬─────┘
      ┌───────────┼──────────────┬───────────────┐
      ▼           ▼              ▼               ▼
┌───────────┐ ┌──────────┐ ┌───────────┐   ┌────────────┐
│ Portfolio │ │ Research │ │   Risk    │   │  General   │
│  Agent    │ │  Agent   │ │  Agent    │   │  (small talk,
└─────┬─────┘ └────┬─────┘ └─────┬─────┘   │  clarifying Q)
      │            │             │         └────────────┘
      ▼            ▼             ▼
 [financial    [RAG retrieve  [financial
  tools:       → rerank →     tools: VaR,
  returns,     evidence       drawdown,
  XIRR, ...]   validation]    concentration]
      │            │             │
      └─────┬──────┴──────┬──────┘
            ▼             
     ┌───────────────┐
     │ Self-reflection│  cross-checks every numeric claim in the draft
     │    critic      │  against actual tool outputs; loops back on failure
     └───────┬────────┘
             ▼
     ┌───────────────┐      trade proposed?     ┌────────────────────┐
     │   Synthesis   │ ───────────────────────▶ │ interrupt() → wait  │
     │  (cited, LLM) │                           │ for human approval  │
     └───────┬───────┘                           └──────────┬──────────┘
             ▼                                                ▼
        stream to user                             TradeApproval row
                                                    (approved/rejected)
                                                                ▼
                                                    Broker adapter (paper/live)
```

- **Checkpointing:** LangGraph's Postgres checkpointer persists graph state
  per `thread_id` (= `agent_sessions.id`), so a trade proposal can sit
  `interrupted` for hours/days awaiting human approval and resume exactly
  where it left off.
- **Evidence validation:** the Research Agent's synthesis step is only
  allowed to state a fact if it can attach a `document_chunks` citation;
  the validation node strips/reflows any uncited claim before it reaches
  self-reflection.
- **Self-reflection:** a dedicated critic node re-reads the draft answer and
  the tool call outputs it was based on, flags numeric mismatches or
  unsupported claims, and forces a regeneration (bounded to 2 retries).
- **LLM routing (`agents/llm_router.py`):** primary = OpenAI
  (`gpt-4.1-mini`/`gpt-4.1` depending on task), automatic fallback to Groq
  (`llama-3.3-70b-versatile`) on error/timeout, then Gemini
  (`gemini-2.0-flash`) as the last resort. All three are wrapped behind one
  `ainvoke_with_fallback()` call so graph nodes never depend on a specific
  provider SDK.

## 6. Broker adapter layer

`BrokerAdapter` (ABC) defines: `authenticate`, `get_holdings`, `get_positions`,
`get_funds`, `get_quote`, `place_order`, `get_order_status`, `cancel_order`.
Each broker (`DhanAdapter`, `AngelOneAdapter`, `UpstoxAdapter`, `FyersAdapter`)
implements this against its own documented REST/WebSocket contract; business
logic (portfolio sync, trade approval flow) only ever depends on the ABC, via
`brokers/registry.py::get_adapter(broker, mode)`. A `MockAdapter` implements
the same interface with deterministic fixture data for paper/demo mode, which
is the default for every new `broker_connections` row until a user supplies
real credentials and flips `mode` to `live`.

## 7. RAG pipeline

1. **Ingestion** (`rag/ingestion.py`): PDF/text upload → cleaned text →
   chunked (~800 tokens, 100 overlap) → stored in `document_chunks`.
2. **Embeddings** (`rag/embeddings.py`): OpenAI `text-embedding-3-small`
   (1536-dim) written to the `embedding vector(1536)` pgvector column.
3. **Hybrid retrieval** (`rag/retrieval.py`): combines pgvector cosine
   similarity search with Postgres full-text (`tsvector`) search, merged via
   reciprocal rank fusion.
4. **Reranking** (`rag/rerank.py`): top-k candidates re-scored (LLM-as-judge
   relevance scoring, deterministic tie-breaks) before being handed to the
   Research Agent.
5. **Citations**: every chunk carries `document_id` + `chunk_index`; the
   synthesis node must emit `[n]` markers mapped back to source metadata
   returned to the frontend for display.

## 8. Frontend information architecture

```
/                      → marketing/redirect
/login, /signup        → Supabase auth flows
/dashboard             → net worth, allocation, daily movers, agent shortcuts
/portfolio             → holdings table, performance chart, risk panel
/portfolio/[id]        → single portfolio detail
/research              → RAG search + document library + citations
/agents                → chat interface (streaming), session history
/agents/[sessionId]    → specific conversation, trade-approval cards inline
/brokers               → connection management (connect/sync/disconnect)
/trade-approvals       → pending/approved/rejected queue, decision actions
/reports               → generated report list + on-demand generation
/settings              → profile, risk tolerance, API keys, security
```

Shared UI system: Tailwind + shadcn/ui primitives, one `components/ui`
design-system layer, `components/charts` (Recharts) and `components/data`
(tables) built on top of it. Every data view has explicit loading (skeleton),
error (retry affordance), and empty (call-to-action) states — never a bare
spinner or blank div.

## 9. Deployment

Local/production runtime is Docker Compose (`infra/docker-compose.yml`):
`frontend`, `backend`, `worker` (Celery), `redis`. Postgres/pgvector is
**Supabase** (hosted), not containerized, so the same connection string works
in dev and prod. CI (`.github/workflows/ci.yml`) runs lint + typecheck + unit
tests for both apps on every PR before a manual deploy step.
