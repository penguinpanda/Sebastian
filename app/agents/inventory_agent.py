"""Inventory Agent — A2A 兼容的库存管理助手。

自然语言库存操作：查询、增删改、过期提醒。
"""

from __future__ import annotations

import logging
from typing import AsyncIterator
from uuid import UUID

from app.a2a.schemas import AgentCard, Artifact, Message, Task
from app.agents.base import BaseAgent
from app.context.budget import ContextBudget
from app.schemas.inventory import InventoryAdjust, InventoryCreate
from app.services.inventory_service import InventoryService

logger = logging.getLogger(__name__)


class InventoryAgent(BaseAgent):
    """库存管理 Agent。"""

    agent_card = AgentCard(
        name="Inventory Agent",
        description="库存管理助手 — 食材增删改查、过期提醒、库存统计",
        url="http://localhost:8000/a2a",
    )

    def __init__(self, service: InventoryService | None = None) -> None:
        super().__init__()
        self._service = service or InventoryService()

    # ── 兼容旧接口 ──────────────────────────────────────────────

    def create_item(self, payload: InventoryCreate):
        return self._service.create_item(payload)

    def adjust_item(self, item_id: UUID, payload: InventoryAdjust):
        return self._service.adjust_item(item_id, payload)

    def list_items(self, user_id: str | None = None, item_type: str | None = None):
        return self._service.list_items(user_id=user_id, item_type=item_type)

    def summary(self, days: int = 7, user_id: str | None = None):
        return self._service.summary(days, user_id=user_id)

    def expiring_items(self, days: int = 7, user_id: str | None = None):
        return self._service.expiring_items(days, user_id=user_id)

    # ── A2A 接口 ────────────────────────────────────────────────

    async def execute(
        self,
        task: Task,
        message: Message,
        llm_messages: list[dict[str, str]],
        budget: ContextBudget,
    ) -> AsyncIterator[Artifact]:
        """A2A 异步处理入口。"""
        params = self._extract_skill_params(message)
        user_id = message.metadata.get("user_id", params.get("user_id", ""))
        skill_id = message.metadata.get("skill_id", params.get("skill_id", "inventory.query"))

        try:
            if skill_id == "inventory.summary":
                result = self._service.summary(days=7, user_id=user_id)
                yield Artifact.from_text(
                    f"库存概况：共 {result.total_items} 件物品，其中 {result.expiring_soon} 件即将过期",
                    metadata=result.model_dump(),
                )

            elif skill_id == "inventory.expiring":
                days = params.get("days", 7)
                items = self._service.expiring_items(days=days, user_id=user_id)
                if not items:
                    yield Artifact.from_text(f"未来 {days} 天内没有即将过期的食材 🎉")
                else:
                    lines = [f"⚠️ 未来 {days} 天内即将过期 ({len(items)} 件)："]
                    for item in items:
                        lines.append(f"  • {item.name} — {item.quantity}{item.unit}（还有 {item.days_left} 天）")
                    yield Artifact.from_text("\n".join(lines))

            elif skill_id == "inventory.query":
                items = self._service.list_items(user_id=user_id)
                if not items:
                    yield Artifact.from_text("库存为空 📭")
                else:
                    lines = [f"📦 库存 ({len(items)} 件)："]
                    for item in items:
                        exp_info = f" — 过期: {item.expire_date}" if item.expire_date else ""
                        lines.append(f"  • {item.name} — {item.quantity}{item.unit}{exp_info}")
                    yield Artifact.from_text("\n".join(lines))

            else:
                yield Artifact.from_text(f"收到库存请求: {message.text[:100]}")

        except Exception as exc:
            logger.exception("Inventory operation failed")
            yield Artifact.from_text(f"库存操作失败: {exc}", metadata={"error": True})
