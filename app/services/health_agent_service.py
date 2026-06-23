from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from app.core.errors import LLMUnavailableError
from app.llm.client import check_llm_available, get_llm_client
from app.schemas.agent_tools import HealthAnalyzeRequest, HealthAnalyzeResponse

logger = logging.getLogger(__name__)


class HealthAgentService:
    @staticmethod
    def _compute_bmi(payload: HealthAnalyzeRequest) -> dict[str, Any]:
        """纯数学计算 BMI 及相关指标，不涉及自然语言生成。"""
        height_m = payload.height_cm / 100.0
        bmi = payload.weight_kg / (height_m * height_m)

        if bmi < 18.5:
            category = "underweight"
            base_calories = 2200
        elif bmi < 24:
            category = "normal"
            base_calories = 2000
        elif bmi < 28:
            category = "overweight"
            base_calories = 1800
        else:
            category = "obese"
            base_calories = 1600

        if payload.target_weight_kg and payload.target_weight_kg < payload.weight_kg:
            base_calories = max(1300, base_calories - 150)

        return {
            "bmi": round(bmi, 2),
            "bmi_category": category,
            "suggested_daily_calories": base_calories,
        }

    @staticmethod
    def _generate_advice_with_llm(
        bmi_data: dict[str, Any],
        payload: HealthAnalyzeRequest,
        meal_history: list[dict[str, Any]] | None = None,
        user_profile: dict[str, Any] | None = None,
    ) -> str:
        """调用 LLM 根据用户完整数据生成个性化健康建议。"""
        check_llm_available()

        context_parts = [
            f"BMI: {bmi_data['bmi']}（{bmi_data['bmi_category']}）",
            f"身高: {payload.height_cm} cm",
            f"体重: {payload.weight_kg} kg",
            f"建议日摄入热量: {bmi_data['suggested_daily_calories']} kcal",
        ]
        if payload.target_weight_kg:
            context_parts.append(f"目标体重: {payload.target_weight_kg} kg")

        if meal_history:
            recent = [m for m in meal_history if m.get("confirmed_at") is not None]
            if recent:
                total_cal = sum(m.get("calories", m.get("estimated_calories", 0)) for m in recent)
                days = 7
                avg_daily = total_cal / max(1, days)
                context_parts.append(f"近{days}天共{len(recent)}餐，日均摄入约{int(avg_daily)} kcal")

        if user_profile:
            goal = user_profile.get("health_goal", "")
            if goal:
                goal_labels = {"lose_weight": "减重", "gain_muscle": "增肌", "maintain": "保持"}
                context_parts.append(f"健康目标: {goal_labels.get(goal, goal)}")
            activity = user_profile.get("activity_level", "")
            if activity:
                context_parts.append(f"活动水平: {activity}")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名专业的健康与营养顾问。根据用户的 BMI 数据、饮食记录和健康目标，"
                    "给出个性化、可操作的健康建议。用中文回复，简洁专业（200字以内），"
                    "避免使用模板化语言，针对具体数据给出具体建议。"
                ),
            },
            {
                "role": "user",
                "content": "用户健康数据：\n" + "\n".join(context_parts) + "\n\n请给出个性化健康分析和建议。",
            },
        ]

        try:
            return get_llm_client().chat(messages, temperature=0.4, max_tokens=500)
        except Exception as exc:
            logger.warning("Health advice LLM generation failed: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

    @staticmethod
    def analyze(payload: HealthAnalyzeRequest) -> HealthAnalyzeResponse:
        """分析用户健康数据：BMI 由公式计算，建议由 LLM 生成。"""
        bmi_data = HealthAgentService._compute_bmi(payload)
        advice = HealthAgentService._generate_advice_with_llm(bmi_data, payload)
        return HealthAnalyzeResponse(
            bmi=bmi_data["bmi"],
            bmi_category=bmi_data["bmi_category"],
            suggested_daily_calories=bmi_data["suggested_daily_calories"],
            advice=advice,
        )

    @staticmethod
    def analyze_with_history(
        payload: HealthAnalyzeRequest,
        meal_history: list[dict[str, Any]],
        days: int = 7,
        user_profile: dict[str, Any] | None = None,
    ) -> HealthAnalyzeResponse:
        """在 BMI 计算基础上，叠加饮食历史和用户档案，由 LLM 生成综合建议。"""
        bmi_data = HealthAgentService._compute_bmi(payload)
        advice = HealthAgentService._generate_advice_with_llm(
            bmi_data, payload, meal_history=meal_history, user_profile=user_profile,
        )
        return HealthAnalyzeResponse(
            bmi=bmi_data["bmi"],
            bmi_category=bmi_data["bmi_category"],
            suggested_daily_calories=bmi_data["suggested_daily_calories"],
            advice=advice,
        )

