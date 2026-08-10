# FINMIND — AI Investment Research & Portfolio Analyst

FINMIND connects to your brokerage accounts, tracks your portfolio, and gives
you an AI research analyst (LangGraph agents) grounded in deterministic
financial math and cited source documents — never live-trading without your
explicit approval.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design,
[`docs/DATABASE_SCHEMA.sql`](docs/DATABASE_SCHEMA.sql) for the Postgres/pgvector
schema, and [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md) for the REST/SSE
API.

## Stack

- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui
- **Backend:** FastAPI + SQLAlchemy (async) + Celery + Redis
- **Database:** Supabase (Postgres + pgvector + Auth + Storage)
- **Agents:** LangGraph, deterministic financial tools, RAG with hybrid
  retrieval + reranking
- **LLM providers:** OpenAI (primary) → Groq (fallback) → Gemini (fallback)
- **Brokers:** DhanHQ, Angel One SmartAPI, Upstox, FYERS — pluggable adapters,
  paper/mock mode by default

## Getting started

### 1. Provision Supabase

1. Create a project at supabase.com.
2. Run [`docs/DATABASE_SCHEMA.sql`](docs/DATABASE_SCHEMA.sql) in the SQL editor.
3. Copy the project URL, anon key, service role key, and JWT secret.

### 2. Configure environment

```bash
cp backend/.env.example backend/.env      # fill in Supabase + LLM + broker keys
cp frontend/.env.example frontend/.env.local
```

### 3. Run

```bash
docker compose -f infra/docker-compose.yml up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1 (docs at `/docs`)

**Running the backend directly on Windows (outside Docker):** you must pass
a custom event loop factory, or the LangGraph Postgres checkpointer will
fail to connect. uvicorn's built-in `asyncio` loop setting hardcodes
`ProactorEventLoop` on Windows, which `psycopg`'s async mode cannot use —
this doesn't affect the Docker/Linux path above.

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --loop app.core.loop:selector_event_loop_factory
```

### 4. Run tests

```bash
# backend
cd backend && python -m pytest

# frontend
cd frontend && npm run test
```

## Repository layout

```
frontend/   Next.js app
backend/    FastAPI app (agents, brokers, rag, financial tools, api)
infra/      docker-compose.yml
docs/       architecture, schema, API contracts
.github/    CI workflows
```

## Safety model

- All financial arithmetic is computed by deterministic, unit-tested Python
  (`backend/app/financial/`) — the LLM only narrates results, never computes them.
- Every new broker connection starts in **paper mode**. Live trading requires
  explicit credentials, an explicit mode switch, and a per-order human
  approval (`trade_approvals` table) before any order reaches a real broker.
