"""UserProfile — 用户健康档案，替代前端传临时参数。"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Float, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserProfile(TimestampMixin, Base):
    """每个 user_id 一条记录，HealthAgent 从此读取而非依赖前端传参。"""

    __tablename__ = "user_profiles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)  # male / female / other
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # low / medium / high
    health_goal: Mapped[str | None] = mapped_column(String(40), nullable=True)  # lose_weight / maintain / gain_muscle
