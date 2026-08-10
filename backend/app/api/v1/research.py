"""One-shot RAG query endpoint — hybrid_search -> rerank -> cited synthesis,
no LangGraph agent session involved (see app/services/research_service.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.schemas.research import ResearchQueryRequest, ResearchQueryResponse
from app.services import research_service

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(rate_limit_dependency)])


@router.post("/query", response_model=ResearchQueryResponse)
async def query_research(
    payload: ResearchQueryRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ResearchQueryResponse:
    result = await research_service.answer_query(payload.query, user_id, db)
    return ResearchQueryResponse(answer=result.answer, citations=result.citations)
