from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class CitationResponse(BaseModel):
    marker: int
    document_id: str
    document_title: str
    chunk_id: str
    chunk_index: int
    snippet: str

    model_config = {"from_attributes": True}


class ResearchQueryResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
