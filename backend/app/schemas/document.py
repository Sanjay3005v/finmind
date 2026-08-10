from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    title: str
    source_type: str
    source_url: Optional[str] = None
    storage_path: Optional[str] = None
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}
