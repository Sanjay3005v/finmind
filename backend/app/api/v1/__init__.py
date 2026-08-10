from fastapi import APIRouter

from app.api.v1 import agents, broker_connections, documents, health, me, portfolios, reports, research, trade_approvals

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(portfolios.router)
api_router.include_router(broker_connections.router)
api_router.include_router(documents.router)
api_router.include_router(research.router)
api_router.include_router(agents.router)
api_router.include_router(trade_approvals.router)
api_router.include_router(reports.router)

__all__ = ["api_router"]
