from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.portfolio import AllocationResponse, PerformanceResponse

REPORT_JOB_STATUSES = ("queued", "running", "ready", "error")


class ReportJobResponse(BaseModel):
    job_id: UUID
    status: str
    download_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportSummaryResponse(BaseModel):
    portfolio_id: UUID
    generated_at: datetime
    performance: PerformanceResponse
    allocation: AllocationResponse
