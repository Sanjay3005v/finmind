# FINMIND — AI Investment Research & Portfolio Analyst

FINMIND connects to your brokerage accounts, tracks your portfolio, and gives
you an AI research analyst (LangGraph agents) grounded in deterministic
financial math and cited source documents — never live-trading without your
explicit approval.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design,
[`docs/DATABASE_SCHEMA.sql`](docs/DATABASE_SCHEMA.sql) for the Postgres/pgvector
schema, and [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md) for the REST/SSE
API.

## Live deployment

| | |
| --- | --- |
| **App** | https://finmind-self.vercel.app |
| **Backend API** | https://finmind-backend-5tk9.onrender.com/api/v1 (docs at `/docs`) |
| **Repo** | https://github.com/Sanjay3005v/finmind |

### Demo login

The app is real Supabase auth — anyone can sign up their own account at
`/signup`. A seeded demo account (one portfolio, four holdings) is also
available if you just want to look around:

```
email:    demo@finmind.app
password: see credentials.md (not committed — ask whoever set this up)
```

The password isn't written into this file since it's a real, working
credential; it's saved in `credentials.md`, which is git-ignored. If you
don't have that file, sign up a fresh account instead — it's the same app.

### Hosting

| Layer | Provider | Plan | Notes |
| --- | --- | --- | --- |
| Frontend | [Vercel](https://vercel.com) | Free (Hobby) | Auto-builds from `frontend/` on every push to `master` once Git integration is connected in the Vercel dashboard; currently deployed via `vercel --prod` from the CLI |
| Backend | [Render](https://render.com) | Free | Deployed from [`render.yaml`](render.yaml) (Blueprint) — Docker build from `backend/Dockerfile`. Free web services spin down after ~15 min idle; the first request after that takes 30–60s to wake back up |
| Database + Auth | [Supabase](https://supabase.com) | existing project | Postgres + pgvector + Auth, same project used for local dev |
| Redis | — (not provisioned) | — | Render has no free Redis tier. `RATE_LIMIT` and caching fail open when Redis is unreachable (see `app/core/rate_limit.py`) — the app works correctly without it, just without real rate limiting. Add a free [Upstash](https://upstash.com) Redis URL as `REDIS_URL` in Render's dashboard if you want it |

**Redeploying:**

```bash
# Frontend — from frontend/, after linking with `vercel link`
vercel --prod

# Backend — push to master; if Render's GitHub auto-deploy is connected it
# redeploys automatically, otherwise trigger a manual deploy from the
# Render dashboard (or "Clear build cache & deploy" after a Dockerfile change)
git push
```

**Environment variables set directly in each provider's dashboard** (never
committed): Vercel holds `NEXT_PUBLIC_SUPABASE_URL` /
`NEXT_PUBLIC_SUPABASE_ANON_KEY` / `NEXT_PUBLIC_API_BASE_URL`; Render holds
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`SUPABASE_JWT_SECRET`, `CORS_ORIGINS`, and the three LLM provider keys
(`OPENAI_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY`).

### Known gap

The **Reports** screen (`/reports`) has frontend UI but no backend route —
`generateReport`/`getReportJob` in `lib/api/client.ts` call
`/api/v1/reports/*`, which doesn't exist yet. Generating a report will show
a "Not Found" error until that endpoint is built.

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
