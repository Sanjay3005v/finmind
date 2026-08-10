-- FINMIND database schema — Supabase Postgres
-- Run via Supabase SQL editor or `alembic upgrade head` (backend/alembic mirrors this).
-- auth.users is managed by Supabase Auth; everything below lives in `public`.

create extension if not exists vector;
create extension if not exists pgcrypto;

-- ─────────────────────────────────────────────────────────────────────────
-- Profiles
-- ─────────────────────────────────────────────────────────────────────────
create table public.profiles (
  user_id           uuid primary key references auth.users(id) on delete cascade,
  full_name         text,
  risk_tolerance    text not null default 'moderate'
                      check (risk_tolerance in ('conservative','moderate','aggressive')),
  investment_horizon_years smallint,
  base_currency     text not null default 'INR',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────────────
-- Portfolios / Holdings / Transactions
-- ─────────────────────────────────────────────────────────────────────────
create table public.portfolios (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  name          text not null,
  base_currency text not null default 'INR',
  is_default    boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index idx_portfolios_user on public.portfolios(user_id);

create table public.broker_connections (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  broker                text not null check (broker in ('dhan','angelone','upstox','fyers')),
  mode                  text not null default 'paper' check (mode in ('paper','live')),
  status                text not null default 'disconnected'
                          check (status in ('disconnected','connected','error','expired')),
  encrypted_credentials bytea,                 -- app-level AES-GCM envelope, never plaintext
  label                 text,
  last_synced_at        timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
create index idx_broker_conn_user on public.broker_connections(user_id);

create table public.holdings (
  id                  uuid primary key default gen_random_uuid(),
  portfolio_id        uuid not null references public.portfolios(id) on delete cascade,
  broker_connection_id uuid references public.broker_connections(id) on delete set null,
  symbol              text not null,
  exchange            text not null default 'NSE',
  quantity            numeric(18,4) not null,
  avg_price           numeric(18,4) not null,
  current_price       numeric(18,4),
  asset_class         text not null default 'equity'
                        check (asset_class in ('equity','etf','mutual_fund','bond','cash','commodity','crypto')),
  sector              text,
  currency            text not null default 'INR',
  updated_at          timestamptz not null default now()
);
create index idx_holdings_portfolio on public.holdings(portfolio_id);
create unique index uq_holdings_portfolio_symbol on public.holdings(portfolio_id, symbol, exchange);

create table public.transactions (
  id               uuid primary key default gen_random_uuid(),
  portfolio_id     uuid not null references public.portfolios(id) on delete cascade,
  symbol           text not null,
  exchange         text not null default 'NSE',
  side             text not null check (side in ('buy','sell')),
  quantity         numeric(18,4) not null,
  price            numeric(18,4) not null,
  fees             numeric(18,4) not null default 0,
  executed_at      timestamptz not null,
  source           text not null default 'manual'
                     check (source in ('broker_sync','manual','agent_trade')),
  broker_order_id  text,
  created_at       timestamptz not null default now()
);
create index idx_transactions_portfolio on public.transactions(portfolio_id, executed_at desc);

-- ─────────────────────────────────────────────────────────────────────────
-- Watchlists
-- ─────────────────────────────────────────────────────────────────────────
create table public.watchlists (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  name       text not null,
  created_at timestamptz not null default now()
);

create table public.watchlist_items (
  id           uuid primary key default gen_random_uuid(),
  watchlist_id uuid not null references public.watchlists(id) on delete cascade,
  symbol       text not null,
  exchange     text not null default 'NSE',
  added_at     timestamptz not null default now()
);
create unique index uq_watchlist_symbol on public.watchlist_items(watchlist_id, symbol, exchange);

-- ─────────────────────────────────────────────────────────────────────────
-- RAG: documents + chunks (pgvector)
-- ─────────────────────────────────────────────────────────────────────────
create table public.documents (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade,  -- null = global/shared corpus
  title        text not null,
  source_type  text not null default 'manual_upload'
                 check (source_type in ('filing','report','news','manual_upload')),
  source_url   text,
  storage_path text,                          -- Supabase Storage object path
  status       text not null default 'pending'
                 check (status in ('pending','processing','ready','failed')),
  uploaded_at  timestamptz not null default now()
);
create index idx_documents_user on public.documents(user_id);

create table public.document_chunks (
  id            uuid primary key default gen_random_uuid(),
  document_id   uuid not null references public.documents(id) on delete cascade,
  chunk_index   int not null,
  content       text not null,
  embedding     vector(1536),
  tsv           tsvector generated always as (to_tsvector('english', content)) stored,
  metadata      jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);
create index idx_chunks_document on public.document_chunks(document_id);
create index idx_chunks_tsv on public.document_chunks using gin(tsv);
create index idx_chunks_embedding on public.document_chunks
  using hnsw (embedding vector_cosine_ops);

-- ─────────────────────────────────────────────────────────────────────────
-- Agent sessions / messages (LangGraph checkpointer keeps its own tables
-- under the `langgraph_*` prefix — created automatically by
-- AsyncPostgresSaver.setup(); not defined here.)
-- ─────────────────────────────────────────────────────────────────────────
create table public.agent_sessions (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  portfolio_id uuid references public.portfolios(id) on delete set null,
  title        text not null default 'New research session',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index idx_agent_sessions_user on public.agent_sessions(user_id);

create table public.agent_messages (
  id          uuid primary key default gen_random_uuid(),
  session_id  uuid not null references public.agent_sessions(id) on delete cascade,
  role        text not null check (role in ('user','assistant','tool','system')),
  content     text not null,
  tool_calls  jsonb,
  citations   jsonb,
  created_at  timestamptz not null default now()
);
create index idx_agent_messages_session on public.agent_messages(session_id, created_at);

-- ─────────────────────────────────────────────────────────────────────────
-- Trade approvals (human-in-the-loop gate before any live order)
-- ─────────────────────────────────────────────────────────────────────────
create table public.trade_approvals (
  id                  uuid primary key default gen_random_uuid(),
  session_id          uuid references public.agent_sessions(id) on delete set null,
  user_id             uuid not null references auth.users(id) on delete cascade,
  broker_connection_id uuid references public.broker_connections(id) on delete set null,
  symbol              text not null,
  exchange            text not null default 'NSE',
  side                text not null check (side in ('buy','sell')),
  quantity            numeric(18,4) not null,
  order_type          text not null default 'market' check (order_type in ('market','limit')),
  limit_price         numeric(18,4),
  status              text not null default 'pending'
                        check (status in ('pending','approved','rejected','expired','executed','failed')),
  requested_by        text not null default 'agent' check (requested_by in ('agent','user')),
  reasoning            text,
  risk_checks         jsonb not null default '{}'::jsonb,
  broker_order_id     text,
  created_at          timestamptz not null default now(),
  decided_at          timestamptz,
  executed_at         timestamptz
);
create index idx_trade_approvals_user on public.trade_approvals(user_id, status);

-- ─────────────────────────────────────────────────────────────────────────
-- Risk snapshots + audit log
-- ─────────────────────────────────────────────────────────────────────────
create table public.risk_assessments (
  id                 uuid primary key default gen_random_uuid(),
  portfolio_id       uuid not null references public.portfolios(id) on delete cascade,
  volatility_annual  numeric(10,6),
  sharpe_ratio       numeric(10,6),
  sortino_ratio      numeric(10,6),
  max_drawdown       numeric(10,6),
  beta               numeric(10,6),
  var_95             numeric(18,4),
  concentration_score numeric(6,4),
  computed_at        timestamptz not null default now()
);
create index idx_risk_portfolio on public.risk_assessments(portfolio_id, computed_at desc);

create table public.audit_log (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references auth.users(id) on delete set null,
  actor         text not null check (actor in ('user','agent','system')),
  action        text not null,
  resource_type text not null,
  resource_id   uuid,
  metadata      jsonb not null default '{}'::jsonb,
  ip_address    text,
  created_at    timestamptz not null default now()
);
create index idx_audit_user on public.audit_log(user_id, created_at desc);

-- ─────────────────────────────────────────────────────────────────────────
-- Row Level Security — enabled on every user-owned table.
-- Backend connects with the Supabase service role for sync jobs; RLS is
-- the defense-in-depth boundary for any direct/anon access path.
-- ─────────────────────────────────────────────────────────────────────────
alter table public.profiles            enable row level security;
alter table public.portfolios          enable row level security;
alter table public.broker_connections  enable row level security;
alter table public.holdings            enable row level security;
alter table public.transactions        enable row level security;
alter table public.watchlists          enable row level security;
alter table public.watchlist_items     enable row level security;
alter table public.documents           enable row level security;
alter table public.agent_sessions      enable row level security;
alter table public.agent_messages      enable row level security;
alter table public.trade_approvals     enable row level security;
alter table public.risk_assessments    enable row level security;
alter table public.audit_log           enable row level security;

create policy "own profile" on public.profiles
  for all using (user_id = auth.uid());

create policy "own portfolios" on public.portfolios
  for all using (user_id = auth.uid());

create policy "own broker connections" on public.broker_connections
  for all using (user_id = auth.uid());

create policy "own holdings" on public.holdings
  for all using (portfolio_id in (select id from public.portfolios where user_id = auth.uid()));

create policy "own transactions" on public.transactions
  for all using (portfolio_id in (select id from public.portfolios where user_id = auth.uid()));

create policy "own watchlists" on public.watchlists
  for all using (user_id = auth.uid());

create policy "own watchlist items" on public.watchlist_items
  for all using (watchlist_id in (select id from public.watchlists where user_id = auth.uid()));

create policy "own or shared documents" on public.documents
  for select using (user_id = auth.uid() or user_id is null);
create policy "manage own documents" on public.documents
  for insert with check (user_id = auth.uid());
create policy "update own documents" on public.documents
  for update using (user_id = auth.uid());
create policy "delete own documents" on public.documents
  for delete using (user_id = auth.uid());

create policy "own agent sessions" on public.agent_sessions
  for all using (user_id = auth.uid());

create policy "own agent messages" on public.agent_messages
  for all using (session_id in (select id from public.agent_sessions where user_id = auth.uid()));

create policy "own trade approvals" on public.trade_approvals
  for all using (user_id = auth.uid());

create policy "own risk assessments" on public.risk_assessments
  for all using (portfolio_id in (select id from public.portfolios where user_id = auth.uid()));

create policy "own audit log" on public.audit_log
  for select using (user_id = auth.uid());

-- document_chunks inherits visibility through its parent document; enforce
-- via a security-definer view rather than RLS on the chunk table itself,
-- since retrieval needs to join across all chunks for a visible document.
alter table public.document_chunks enable row level security;
create policy "chunks of visible documents" on public.document_chunks
  for select using (
    document_id in (
      select id from public.documents where user_id = auth.uid() or user_id is null
    )
  );
