"""Agent Card — A2A Agent 元数据持久化。

存储每个 Agent Card 的完整 JSON 定义，支持运行时发现和注册。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentCardRegistry(Base):
    """持久化的 Agent Card 注册表。"""

    __tablename__ = "agent_cards"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="Agent 名称（如 recipe, health）")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Agent 展示名称")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="Agent 描述")
    card_json: Mapped[dict] = mapped_column(JSON, nullable=False, comment="完整 Agent Card JSON")
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="0.1.0", comment="Agent Card 版本")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
