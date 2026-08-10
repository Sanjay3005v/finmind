from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

RiskTolerance = Literal["conservative", "moderate", "aggressive"]


class ProfileResponse(BaseModel):
    user_id: UUID
    full_name: Optional[str] = None
    risk_tolerance: RiskTolerance
    investment_horizon_years: Optional[int] = None
    base_currency: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    risk_tolerance: Optional[RiskTolerance] = None
    investment_horizon_years: Optional[int] = Field(default=None, ge=0, le=100)
    base_currency: Optional[str] = None
