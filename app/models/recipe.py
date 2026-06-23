"""Recipe — 已验证菜谱库，避免每次 LLM 重复生成。"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Float, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Recipe(TimestampMixin, Base):
    """用户确认制作的菜谱自动入库，SearchAgent 可从此库检索。"""

    __tablename__ = "recipes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    estimated_calories: Mapped[int] = mapped_column(Integer, default=0)
    ingredients: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # [{"name": "鸡胸肉", "amount": 200, "unit": "g"}]
    steps: Mapped[dict | None] = mapped_column(JSON, nullable=True)        # ["step1", "step2"]
    required_equipment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recipe_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 完整 RecipeRecommendResponse
    times_made: Mapped[int] = mapped_column(Integer, default=1)            # 制作次数，用于排序
    content_hash: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # MD5 去重指纹
