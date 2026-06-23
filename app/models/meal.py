"""MealHistory — 用户确认制作菜谱后的饮食记录。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Float, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MealHistory(TimestampMixin, Base):
    """用户每次确认制作菜谱后写入一条记录，供 HealthAgent 分析饮食历史。"""

    __tablename__ = "meal_history"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    meal_date: Mapped[date] = mapped_column(Date, nullable=False, default=lambda: date.today())
    recipe_title: Mapped[str] = mapped_column(String(200), nullable=False)
    estimated_calories: Mapped[int] = mapped_column(default=0)
    recipe_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deducted_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # [{name, amount, unit, inventory_name, inventory_id}]
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
