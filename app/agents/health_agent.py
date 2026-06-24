"""Health Agent — A2A 兼容的健康分析助手。

BMI 纯数学计算 + LLM 个性化健康建议生成。
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from app.a2a.schemas import AgentCard, Artifact, Message, Task
from app.agents.base import BaseAgent
from app.context.budget import ContextBudget
from app.core.errors import LLMUnavailableError
from app.llm.client import check_llm_available, get_llm_client

logger = logging.getLogger(__name__)


class HealthAgent(BaseAgent):
    """健康分析 Agent。

    流程: BMI 公式计算 → LLM 个性化建议（可叠加饮食历史）。
    """

    agent_card = AgentCard(
        name="Health Agent",
        description="健康分析助手 — BMI 计算、饮食热量分析、个性化健康建议",
        url="http://localhost:8000/a2a",
    )

    def __init__(self) -> None:
        super().__init__()
        self._db = None  # 用于注入测试数据库会话

    # ── 兼容旧接口 ──────────────────────────────────────────────

    def analyze(
        self,
        payload,
        meal_history: list[dict[str, Any]] | None = None,
        days: int = 7,
    ):
        """旧同步接口兼容层。"""
        from app.services.health_agent_service import HealthAgentService
        if meal_history:
            return HealthAgentService.analyze_with_history(payload, meal_history, days)
        return HealthAgentService.analyze(payload)

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
        user_id = message.metadata.get("user_id", params.get("user_id", "default"))

        height_cm = params.get("height_cm", 170)
        weight_kg = params.get("weight_kg", 65)
        target_weight_kg = params.get("target_weight_kg")

        # BMI 纯数学计算
        bmi_data = self._compute_bmi(height_cm, weight_kg, target_weight_kg)

        # 加载饮食历史
        meal_history = await self._load_meal_history(user_id, days=7)
        user_profile = await self._load_user_profile(user_id)

        # LLM 建议
        advice = await self._generate_advice(bmi_data, height_cm, weight_kg, target_weight_kg, meal_history, user_profile)

        result_text = (
            f"健康分析结果：\n"
            f"BMI: {bmi_data['bmi']} ({bmi_data['bmi_category']})\n"
            f"建议日摄入: {bmi_data['suggested_daily_calories']} kcal\n"
            f"{advice}"
        )

        yield Artifact.from_text(
            result_text,
            metadata={
                "bmi": bmi_data["bmi"],
                "bmi_category": bmi_data["bmi_category"],
                "suggested_daily_calories": bmi_data["suggested_daily_calories"],
            },
        )

    # ── 核心计算 ────────────────────────────────────────────────

    @staticmethod
    def _compute_bmi(height_cm: float, weight_kg: float, target_weight_kg: float | None) -> dict:
        """纯数学 BMI 计算。"""
        height_m = height_cm / 100.0
        bmi = weight_kg / (height_m * height_m)

        if bmi < 18.5:
            category, base_cal = "underweight", 2200
        elif bmi < 24:
            category, base_cal = "normal", 2000
        elif bmi < 28:
            category, base_cal = "overweight", 1800
        else:
            category, base_cal = "obese", 1600

        if target_weight_kg and target_weight_kg < weight_kg:
            base_cal = max(1300, base_cal - 150)

        return {"bmi": round(bmi, 2), "bmi_category": category, "suggested_daily_calories": base_cal}

    async def _load_meal_history(self, user_id: str, days: int = 7) -> list[dict[str, Any]]:
        """加载最近 N 天的饮食历史。"""
        try:
            if self._db is None:
                from app.db.session import get_session_factory
                self._db = next(get_session_factory()())
            from sqlalchemy import select
            from datetime import date, timedelta
            from app.models.meal import MealHistory

            since = date.today() - timedelta(days=days)
            stmt = select(MealHistory).where(
                MealHistory.user_id == user_id,
                MealHistory.meal_date >= since,
                MealHistory.confirmed_at.isnot(None),
            )
            rows = self._db.execute(stmt).scalars().all()
            return [{"title": r.recipe_title, "calories": r.estimated_calories, "confirmed_at": r.confirmed_at} for r in rows]
        except Exception:
            return []

    async def _load_user_profile(self, user_id: str) -> dict[str, Any] | None:
        """加载用户档案。"""
        try:
            if self._db is None:
                from app.db.session import get_session_factory
                self._db = next(get_session_factory()())
            from app.models.user_profile import UserProfile

            profile = self._db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            if profile:
                return {
                    "health_goal": getattr(profile, "health_goal", ""),
                    "activity_level": getattr(profile, "activity_level", ""),
                    "classification": getattr(profile, "classification", ""),
                    "preferences": getattr(profile, "preferences", {}),
                }
        except Exception:
            pass
        return None

    async def _generate_advice(
        self,
        bmi_data: dict,
        height_cm: float,
        weight_kg: float,
        target_weight_kg: float | None,
        meal_history: list[dict],
        user_profile: dict | None,
    ) -> str:
        """LLM 生成个性化建议。"""
        check_llm_available()

        context_parts = [
            f"BMI: {bmi_data['bmi']}（{bmi_data['bmi_category']}）",
            f"身高: {height_cm} cm, 体重: {weight_kg} kg",
            f"建议日摄入热量: {bmi_data['suggested_daily_calories']} kcal",
        ]
        if target_weight_kg:
            context_parts.append(f"目标体重: {target_weight_kg} kg")

        if meal_history:
            recent = [m for m in meal_history if m.get("confirmed_at")]
            if recent:
                total_cal = sum(m.get("calories", 0) for m in recent)
                avg_daily = total_cal / max(1, 7)
                context_parts.append(f"近7天共{len(recent)}餐，日均摄入约{int(avg_daily)} kcal")

        messages = [
            {"role": "system", "content": "你是专业的健康与营养顾问。用中文给出简洁专业、可操作的建议（200字以内）。"},
            {"role": "user", "content": "用户健康数据：\n" + "\n".join(context_parts) + "\n\n请给出个性化健康分析和建议。"},
        ]

        try:
            return get_llm_client().chat(messages, temperature=0.4, max_tokens=500)
        except Exception as exc:
            logger.warning("Health advice LLM failed: %s", exc)
            return f"健康建议生成失败: {exc}"
