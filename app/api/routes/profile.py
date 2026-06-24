"""UserProfile API — 用户健康档案的创建、更新和查询。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.models.user_profile import UserProfile
from app.schemas.search import MemoryCreateRequest
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile")


class PreferencesSchema(BaseModel):
    """用户偏好结构：饮食、生活方式、菜系、厨具、自由文本。"""
    dietary: list[str] = Field(default_factory=list, description="饮食偏好标签，如 [辣, 清淡, 低碳水]")
    lifestyle: list[str] = Field(default_factory=list, description="生活方式标签，如 [早起, 运动]")
    cuisine: list[str] = Field(default_factory=list, description="菜系偏好，如 [川菜, 日料]")
    equipment: list[str] = Field(default_factory=list, description="常用厨具，如 [炒锅, 电饭煲, 空气炸锅]")
    free_text: str = Field(default="", max_length=2000, description="自由文本补充")


class UserProfileRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    classification: str | None = Field(default=None, pattern="^(single_male|single_female)$")
    preferences: PreferencesSchema | None = Field(default=None)
    age: int | None = Field(default=None, ge=1, le=120)
    gender: str | None = Field(default=None, pattern="^(male|female|other)$")
    height_cm: float | None = Field(default=None, gt=50, le=250)
    weight_kg: float | None = Field(default=None, gt=20, le=400)
    activity_level: str | None = Field(default=None, pattern="^(low|medium|high)$")
    health_goal: str | None = Field(default=None, max_length=40)


class UserProfileResponse(BaseModel):
    user_id: str
    classification: str | None
    preferences: dict[str, Any] | None
    age: int | None
    gender: str | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: str | None
    health_goal: str | None
    updated_at: str


def _preferences_to_dict(prefs: PreferencesSchema | None) -> dict[str, Any] | None:
    """将 PreferencesSchema 转为普通 dict，用于存储到 JSONB。"""
    if prefs is None:
        return None
    return {
        "dietary": prefs.dietary,
        "lifestyle": prefs.lifestyle,
        "cuisine": prefs.cuisine,
        "equipment": prefs.equipment,
        "free_text": prefs.free_text,
    }


def _build_preferences_memory_content(
    user_id: str,
    classification: str | None,
    prefs: dict[str, Any] | None,
    age: int | None = None,
    gender: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    activity_level: str | None = None,
    health_goal: str | None = None,
) -> str:
    """将分类、偏好和健康数据拼接为可检索的记忆文本。"""
    parts: list[str] = [f"用户 {user_id} 的偏好记录："]
    if classification:
        label = "单身男性" if classification == "single_male" else "单身女性"
        parts.append(f"分类: {label}")
    if prefs:
        dietary = prefs.get("dietary", [])
        if dietary:
            parts.append(f"饮食偏好: {', '.join(dietary)}")
        lifestyle = prefs.get("lifestyle", [])
        if lifestyle:
            parts.append(f"生活方式: {', '.join(lifestyle)}")
        cuisine = prefs.get("cuisine", [])
        if cuisine:
            parts.append(f"菜系偏好: {', '.join(cuisine)}")
        free_text = prefs.get("free_text", "")
        if free_text:
            parts.append(f"补充: {free_text}")
    # 健康数据
    health_parts: list[str] = []
    if age is not None:
        health_parts.append(f"年龄: {age}岁")
    if gender:
        gender_label = {"male": "男", "female": "女", "other": "其他"}.get(gender, gender)
        health_parts.append(f"性别: {gender_label}")
    if height_cm is not None:
        health_parts.append(f"身高: {height_cm}cm")
    if weight_kg is not None:
        health_parts.append(f"体重: {weight_kg}kg")
    if activity_level:
        level_label = {"low": "低(久坐)", "medium": "中(日常活动)", "high": "高(经常运动)"}.get(activity_level, activity_level)
        health_parts.append(f"活动水平: {level_label}")
    if health_goal:
        goal_label = {"lose_weight": "减重", "maintain": "维持", "gain_muscle": "增肌"}.get(health_goal, health_goal)
        health_parts.append(f"健康目标: {goal_label}")
    if health_parts:
        parts.append("健康档案: " + "，".join(health_parts))
    return "；".join(parts)


def _index_preferences_to_memory(
    user_id: str,
    classification: str | None,
    prefs: dict[str, Any] | None,
    age: int | None = None,
    gender: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    activity_level: str | None = None,
    health_goal: str | None = None,
) -> None:
    """将偏好和健康数据写入 Elasticsearch 长期记忆。ES 不可用时仅记录 warning，不影响主流程。"""
    content = _build_preferences_memory_content(
        user_id, classification, prefs,
        age=age, gender=gender, height_cm=height_cm, weight_kg=weight_kg,
        activity_level=activity_level, health_goal=health_goal,
    )
    if not content:
        return

    tags: list[str] = ["profile_preference", "健康档案"]
    if classification:
        tags.append(classification)
    if prefs:
        tags.extend(prefs.get("dietary", []))
        tags.extend(prefs.get("cuisine", []))
    if gender:
        tags.append(gender)
    if activity_level:
        tags.append(activity_level)
    if health_goal:
        tags.append(health_goal)

    try:
        service = SearchService()
        service.index_memory(
            MemoryCreateRequest(
                user_id=user_id,
                memory_type="profile_preference",
                content=content,
                tags=tags,
                importance=0.8,
            ),
        )
        logger.info("Preferences indexed to ES for user %s", user_id)
    except Exception:
        logger.warning("Failed to index preferences to ES for user %s", user_id, exc_info=True)


@router.post("", response_model=UserProfileResponse)
def save_profile(
    payload: UserProfileRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """创建或更新用户健康档案（upsert）。首次保存时同时将偏好写入 ES 长期记忆。"""
    request.state.user_id = payload.user_id
    request.state.action = "save_profile"

    stmt = select(UserProfile).where(UserProfile.user_id == payload.user_id)
    profile = db.execute(stmt).scalars().first()
    is_new = profile is None
    prefs_dict = _preferences_to_dict(payload.preferences)

    if profile:
        profile.classification = payload.classification
        profile.preferences = prefs_dict
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
            classification=payload.classification,
            preferences=prefs_dict,
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

    # 每次保存都将偏好和健康数据写入 ES 长期记忆（可被 Agent 检索和 Memory 页面查看）
    _index_preferences_to_memory(
        payload.user_id, payload.classification, prefs_dict,
        age=payload.age, gender=payload.gender,
        height_cm=payload.height_cm, weight_kg=payload.weight_kg,
        activity_level=payload.activity_level, health_goal=payload.health_goal,
    )

    return UserProfileResponse(
        user_id=profile.user_id,
        classification=profile.classification,
        preferences=profile.preferences,
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
        classification=profile.classification,
        preferences=profile.preferences,
        age=profile.age,
        gender=profile.gender,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        health_goal=profile.health_goal,
        updated_at=profile.updated_at.isoformat(),
    )
