from __future__ import annotations

from app.schemas.agent_tools import HealthAnalyzeRequest, HealthAnalyzeResponse


class HealthAgentService:
    @staticmethod
    def analyze(payload: HealthAnalyzeRequest) -> HealthAnalyzeResponse:
        height_m = payload.height_cm / 100.0
        bmi = payload.weight_kg / (height_m * height_m)

        if bmi < 18.5:
            category = "underweight"
            base_calories = 2200
            advice = "建议提高蛋白质摄入，并每周监测体重变化。"
        elif bmi < 24:
            category = "normal"
            base_calories = 2000
            advice = "建议保持均衡饮食，并维持稳定日常活动量。"
        elif bmi < 28:
            category = "overweight"
            base_calories = 1800
            advice = "建议采用适度热量缺口，并增加每日步行量。"
        else:
            category = "obese"
            base_calories = 1600
            advice = "建议控制热量赤字，必要时寻求专业医生或营养师指导。"

        if payload.target_weight_kg and payload.target_weight_kg < payload.weight_kg:
            base_calories = max(1300, base_calories - 150)

        return HealthAnalyzeResponse(
            bmi=round(bmi, 2),
            bmi_category=category,
            suggested_daily_calories=base_calories,
            advice=advice,
        )
