# FINMIND API Contracts — v1

Base URL: `/api/v1`. All endpoints except `/health` require
`Authorization: Bearer <supabase_access_token>`. Errors follow a single shape:

```json
{ "error": { "code": "PORTFOLIO_NOT_FOUND", "message": "...", "request_id": "..." } }
```

## Health & meta
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness (no auth) |
| GET | `/health/ready` | Readiness — checks DB + Redis (no auth) |
| GET | `/me` | Current user profile |
| PATCH | `/me` | Update risk tolerance / horizon / base currency |

## Portfolios
| Method | Path | Description |
|---|---|---|
| GET | `/portfolios` | List portfolios for current user |
| POST | `/portfolios` | Create a portfolio |
| GET | `/portfolios/{id}` | Portfolio detail |
| GET | `/portfolios/{id}/holdings` | Current holdings snapshot |
| GET | `/portfolios/{id}/transactions` | Paginated transaction history |
| GET | `/portfolios/{id}/performance?range=1M\|3M\|1Y\|ALL` | Time series + CAGR/Sharpe/etc (deterministic tools) |
| GET | `/portfolios/{id}/risk` | Latest `risk_assessments` row + recompute-on-demand flag |
| GET | `/portfolios/{id}/allocation` | Asset-class / sector breakdown |

## Broker connections
| Method | Path | Description |
|---|---|---|
| GET | `/broker-connections` | List connections (credentials never returned) |
| POST | `/broker-connections` | Start connecting a broker (`{broker, mode}` → auth URL or credential form spec) |
| POST | `/broker-connections/{id}/callback` | Complete OAuth/token exchange for the broker |
| POST | `/broker-connections/{id}/sync` | Trigger a background holdings/positions sync (Celery task id returned) |
| DELETE | `/broker-connections/{id}` | Disconnect + purge encrypted credentials |

## Documents & research (RAG)
| Method | Path | Description |
|---|---|---|
| GET | `/documents` | List documents visible to the user |
| POST | `/documents` | Upload a document (multipart) → queued for ingestion |
| GET | `/documents/{id}` | Document detail + ingestion status |
| DELETE | `/documents/{id}` | Remove a document and its chunks |
| POST | `/research/query` | One-shot RAG query `{query}` → `{answer, citations[]}` (no agent session) |

## Agents (LangGraph, streaming)
| Method | Path | Description |
|---|---|---|
| GET | `/agents/sessions` | List sessions for current user |
| POST | `/agents/sessions` | Create a session `{portfolio_id?, title?}` |
| GET | `/agents/sessions/{id}/messages` | Message history |
| POST | `/agents/sessions/{id}/messages` | Send a message; **SSE stream** of `{token}` / `{tool_call}` / `{citation}` / `{interrupt: trade_approval_id}` / `{done}` events |
| POST | `/agents/sessions/{id}/resume` | Resume an interrupted graph after a trade decision |

## Trade approvals (human-in-the-loop)
| Method | Path | Description |
|---|---|---|
| GET | `/trade-approvals?status=pending` | Queue for current user |
| GET | `/trade-approvals/{id}` | Detail incl. `risk_checks` and agent reasoning |
| POST | `/trade-approvals/{id}/decision` | `{decision: "approve"\|"reject", note?}` — only the owning user may decide |

## Reports
| Method | Path | Description |
|---|---|---|
| GET | `/reports/{portfolio_id}/summary` | On-demand JSON report (performance + risk + allocation) |
| POST | `/reports/{portfolio_id}/generate` | Queue a PDF report generation job |
| GET | `/reports/jobs/{job_id}` | Report job status + download URL when ready |

## Streaming event contract (SSE)

```
event: token
data: {"text": "Based on your portfolio's"}

event: tool_call
data: {"name": "compute_sharpe_ratio", "args": {...}, "result": {...}}

event: citation
data: {"chunk_id": "...", "document_title": "...", "snippet": "..."}

event: interrupt
data: {"trade_approval_id": "...", "symbol": "RELIANCE", "side": "buy", "quantity": 10}

event: done
data: {"message_id": "..."}
```

The frontend renders `tool_call` events as inline "checked your portfolio"
chips (never raw JSON), `citation` events as numbered source pills, and
`interrupt` as a blocking trade-approval card that must be resolved via
`POST /trade-approvals/{id}/decision` before the conversation can continue.
