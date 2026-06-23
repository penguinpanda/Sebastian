"""UserProfile API — 用户健康档案的创建、更新和查询。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/profile")


class UserProfileRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    age: int | None = Field(default=None, ge=1, le=120)
    gender: str | None = Field(default=None, pattern="^(male|female|other)$")
    height_cm: float | None = Field(default=None, gt=50, le=250)
    weight_kg: float | None = Field(default=None, gt=20, le=400)
    activity_level: str | None = Field(default=None, pattern="^(low|medium|high)$")
    health_goal: str | None = Field(default=None, max_length=40)


class UserProfileResponse(BaseModel):
    user_id: str
    age: int | None
    gender: str | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: str | None
    health_goal: str | None
    updated_at: str


@router.post("", response_model=UserProfileResponse)
def save_profile(
    payload: UserProfileRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """创建或更新用户健康档案（upsert）。"""
    request.state.user_id = payload.user_id
    request.state.action = "save_profile"

    stmt = select(UserProfile).where(UserProfile.user_id == payload.user_id)
    profile = db.execute(stmt).scalars().first()

    if profile:
        profile.age = payload.age
        profile.gender = payload.gender
        profile.height_cm = payload.height_cm
        profile.weight_kg = payload.weight_kg
        profile.activity_level = payload.activity_level
        profile.health_goal = payload.health_goal
        profile.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    else:
        profile = UserProfile(
            id=uuid4(),
            user_id=payload.user_id,
            age=payload.age,
            gender=payload.gender,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            activity_level=payload.activity_level,
            health_goal=payload.health_goal,
        )
        db.add(profile)

    db.commit()
    db.refresh(profile)

    return UserProfileResponse(
        user_id=profile.user_id,
        age=profile.age,
        gender=profile.gender,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        health_goal=profile.health_goal,
        updated_at=profile.updated_at.isoformat(),
    )


@router.get("", response_model=UserProfileResponse | dict)
def get_profile(
    user_id: str = Query(min_length=1, max_length=64),
    db: Session = Depends(get_db_session),
) -> UserProfileResponse | dict:
    """查询用户健康档案。"""
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    profile = db.execute(stmt).scalars().first()

    if not profile:
        return {"user_id": user_id, "detail": "not_found"}

    return UserProfileResponse(
        user_id=profile.user_id,
        age=profile.age,
        gender=profile.gender,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        health_goal=profile.health_goal,
        updated_at=profile.updated_at.isoformat(),
    )
