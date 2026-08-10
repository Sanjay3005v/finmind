"""Broker adapter factory — the ONLY place allowed to decide which concrete
class backs a `broker_connections` row.

Hard safety rule: a `paper`-mode connection ALWAYS gets `MockAdapter`, no
matter what `broker` says. The `broker` column on a paper connection is
purely a record of which live broker this connection will map to if/when a
user explicitly promotes it to `mode='live'` (a separate, later-phase flow)
— it must never influence which adapter actually executes calls while the
connection is still paper.
"""
from __future__ import annotations

from app.brokers.angelone import AngelOneAdapter
from app.brokers.base import BrokerAdapter
from app.brokers.dhan import DhanAdapter
from app.brokers.fyers import FyersAdapter
from app.brokers.mock import MockAdapter
from app.brokers.upstox import UpstoxAdapter
from app.core.errors import AppError

_LIVE_ADAPTERS: dict[str, type[BrokerAdapter]] = {
    "dhan": DhanAdapter,
    "angelone": AngelOneAdapter,
    "upstox": UpstoxAdapter,
    "fyers": FyersAdapter,
}


def get_adapter(broker: str, mode: str, credentials: dict | None = None) -> BrokerAdapter:
    """Factory used by `app/services/broker_service.py` (and, later, agent
    trade tools) to obtain a `BrokerAdapter` for a given connection.

    - `mode == "paper"`  -> always `MockAdapter`, regardless of `broker`.
    - `mode == "live"`   -> the real adapter for `broker`, constructed with
                            decrypted `credentials` (falls back to settings
                            env vars for any missing field, per-adapter).
    """
    if mode == "paper":
        return MockAdapter(broker_label=broker)

    if mode != "live":
        raise AppError(code="INVALID_BROKER_MODE", message=f"Unknown broker mode: {mode!r}", status_code=400)

    adapter_cls = _LIVE_ADAPTERS.get(broker)
    if adapter_cls is None:
        raise AppError(code="UNSUPPORTED_BROKER", message=f"Unsupported broker: {broker!r}", status_code=400)
    return adapter_cls(credentials=credentials or {})
