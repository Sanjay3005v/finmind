"""Custom asyncio loop factory for uvicorn on Windows.

uvicorn's built-in "asyncio" loop setting (`uvicorn/loops/asyncio.py`)
unconditionally constructs `asyncio.ProactorEventLoop` on `win32`, ignoring
any event loop policy the application sets — it passes the loop class
directly to `asyncio.run(..., loop_factory=...)`. `psycopg`'s async mode
(used by the LangGraph Postgres checkpointer, see `app/agents/checkpoint.py`)
cannot run on `ProactorEventLoop` at all.

Point uvicorn at this factory instead: `--loop app.core.loop:selector_event_loop_factory`
(see `infra/docker-compose.yml` and the README's local dev instructions).

Note on uvicorn's `--loop` contract: for the built-in names ("asyncio",
"uvloop"), `Config.get_loop_factory()` imports a "factory of factories" and
calls it with `use_subprocess=...` to get the real zero-arg loop factory.
For a *custom* dotted path (this module), uvicorn skips that extra call and
uses the imported object directly as the zero-arg factory — so this function
must itself return a loop *instance* when called with no arguments, not a
factory that needs calling again.
"""
from __future__ import annotations

import asyncio


def selector_event_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()
