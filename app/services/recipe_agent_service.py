from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.errors import LLMError
from app.llm.client import get_llm_client
from app.schemas.agent_tools import RecipeRecommendRequest, RecipeRecommendResponse
from app.services.inventory_service import InventoryService


logger = logging.getLogger(__name__)


class RecipeAgentService:
    def __init__(self, inventory_service: InventoryService | None = None) -> None:
        self._inventory_service = inventory_service or InventoryService()

    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        settings = get_settings()
        if settings.deepseek_api_key:
            llm_result = self._recommend_with_llm(payload)
            if llm_result is not None:
                return llm_result

        return self._recommend_with_template(payload)

    def _recommend_with_llm(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse | None:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名营养导向的菜谱规划助手。仅返回合法 JSON，字段必须是："
                    "title, rationale, estimated_calories, steps, required_equipment, missing_ingredients。"
                    "所有文案使用中文，步骤简洁且可执行。"
                    
                    "要求："
                    "1. required_equipment必须列出制作该菜谱所需全部厨具；"
                    "2. 不允许遗漏厨具；"
                    "3. steps必须与required_equipment一致；"
                    "4. 所有内容使用中文；"
                    "5. 步骤简洁且可执行。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"""
                        用户ID：{payload.user_id}
                        餐食类型：{payload.meal_type}
                        目标热量：{payload.target_calories}
                        用户当前拥有厨具：{', '.join(payload.available_equipment) if payload.available_equipment else '无'}
                        饮食偏好：{', '.join(payload.dietary_preferences) if payload.dietary_preferences else '无'}
                        
                        请生成菜谱。
                        注意：
                        required_equipment 应列出制作该菜谱实际需要的全部厨具，
                        不必局限于用户当前拥有的厨具
                    """
                ),
            },
        ]

        try:
            raw = get_llm_client().chat_json(messages, temperature=0.4, max_tokens=600)
            result = RecipeRecommendResponse.model_validate(raw)
            return result.model_copy(update={"estimated_calories": min(payload.target_calories, result.estimated_calories)})
        except (LLMError, ValueError, TypeError) as exc:
            logger.warning("Recipe LLM generation failed, fallback to template: %s", exc)
            return None

    def _recommend_with_template(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        summary = self._inventory_service.summary(days=7)
        inventory_factor = max(1, summary.total_items)
        estimated = min(payload.target_calories, 350 + inventory_factor * 20)

        meal_type_label = {
            "breakfast": "早餐",
            "lunch": "午餐",
            "dinner": "晚餐",
            "snack": "加餐",
        }.get(payload.meal_type, payload.meal_type)
        title = f"{meal_type_label}能量碗"
        rationale = (
            f"根据你当前库存数量（{summary.total_items}）和饮食偏好，"
            f"该方案将热量控制在约 {estimated} kcal。"
        )
        steps = [
            "优先使用现有库存中的蛋白质和蔬菜进行准备。",
            "采用少油烹饪，并根据口味进行基础调味。",
            "搭配适量主食，保证碳水、蛋白和蔬菜均衡。",
        ]
        missing = [] if summary.total_items > 0 else ["蛋白质食材", "蔬菜"]

        return RecipeRecommendResponse(
            title=title,
            rationale=rationale,
            estimated_calories=estimated,
            steps=steps,
            missing_ingredients=missing,
        )
