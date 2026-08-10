"""GET/PATCH the caller's profile. Created lazily on first GET if missing."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import parse_user_uuid
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest

router = APIRouter(tags=["me"], dependencies=[Depends(rate_limit_dependency)])


async def _get_or_create_profile(db: AsyncSession, user_id: str) -> Profile:
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(select(Profile).where(Profile.user_id == owner_uuid))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = Profile(user_id=owner_uuid)
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
    return profile


@router.get("/me", response_model=ProfileResponse)
async def get_me(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    return await _get_or_create_profile(db, user_id)


@router.patch("/me", response_model=ProfileResponse)
async def update_me(
    payload: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    profile = await _get_or_create_profile(db, user_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    await db.flush()
    await db.refresh(profile)
    return profile
