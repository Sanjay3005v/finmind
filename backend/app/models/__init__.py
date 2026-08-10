"""SQLAlchemy ORM models mirroring docs/DATABASE_SCHEMA.sql exactly.

Import every model module here so that `Base.metadata` (used by Alembic
autogenerate and by tests that `create_all` against sqlite) sees the full
table set with a single `import app.models`.
"""
from app.models import _supabase_auth_stub  # noqa: F401  (registers auth.users stub for FK resolution)
from app.models.profile import Profile
from app.models.portfolio import Portfolio
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.transaction import Transaction
from app.models.watchlist import Watchlist
from app.models.watchlist_item import WatchlistItem
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.agent_session import AgentSession
from app.models.agent_message import AgentMessage
from app.models.trade_approval import TradeApproval
from app.models.risk_assessment import RiskAssessment
from app.models.audit_log import AuditLog

__all__ = [
    "Profile",
    "Portfolio",
    "BrokerConnection",
    "Holding",
    "Transaction",
    "Watchlist",
    "WatchlistItem",
    "Document",
    "DocumentChunk",
    "AgentSession",
    "AgentMessage",
    "TradeApproval",
    "RiskAssessment",
    "AuditLog",
]
