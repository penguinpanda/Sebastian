"""Conversation persistence — 保存和加载对话历史。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.models.conversation import Conversation

router = APIRouter(prefix="/conversations")


class ConversationSaveRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    date: str = Field(description="日期，格式 YYYY-MM-DD")
    messages: list[dict] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    date: str
    messages: list[dict]
    last_active_at: str


class ConversationDatesResponse(BaseModel):
    dates: list[str]


@router.post("/save", response_model=ConversationResponse)
def save_conversation(
    payload: ConversationSaveRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> ConversationResponse:
    """保存当日对话：如已有记录则追加/覆盖 messages，否则新建。"""
    request.state.action = "save_conversation"
    request.state.user_id = payload.user_id

    conv_date = date.fromisoformat(payload.date)

    stmt = select(Conversation).where(
        Conversation.user_id == payload.user_id,
        Conversation.conversation_date == conv_date,
    )
    existing = db.execute(stmt).scalars().first()

    if existing:
        existing.messages = payload.messages
        existing.last_active_at = datetime.now(timezone.utc)
        conv = existing
    else:
        conv = Conversation(
            id=uuid4(),
            user_id=payload.user_id,
            conversation_date=conv_date,
            messages=payload.messages,
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(conv)

    db.commit()
    db.refresh(conv)

    return ConversationResponse(
        id=str(conv.id),
        user_id=conv.user_id,
        date=str(conv.conversation_date),
        messages=conv.messages or [],
        last_active_at=conv.last_active_at.isoformat(),
    )


@router.get("", response_model=ConversationResponse | dict)
def get_conversation(
    user_id: str = Query(min_length=1, max_length=64),
    date_str: str = Query(alias="date", description="日期，格式 YYYY-MM-DD"),
    db: Session = Depends(get_db_session),
) -> ConversationResponse | dict:
    """加载指定日期的对话历史。"""
    conv_date = date.fromisoformat(date_str)

    stmt = select(Conversation).where(
        Conversation.user_id == user_id,
        Conversation.conversation_date == conv_date,
    )
    conv = db.execute(stmt).scalars().first()

    if not conv:
        return {"id": "", "user_id": user_id, "date": date_str, "messages": [], "last_active_at": ""}

    return ConversationResponse(
        id=str(conv.id),
        user_id=conv.user_id,
        date=str(conv.conversation_date),
        messages=conv.messages or [],
        last_active_at=conv.last_active_at.isoformat(),
    )


@router.get("/dates", response_model=ConversationDatesResponse)
def get_conversation_dates(
    user_id: str = Query(min_length=1, max_length=64),
    db: Session = Depends(get_db_session),
) -> ConversationDatesResponse:
    """返回用户有对话记录的所有日期，供左侧历史栏使用。"""
    stmt = (
        select(Conversation.conversation_date)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.conversation_date.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return ConversationDatesResponse(dates=[str(d) for d in rows])
