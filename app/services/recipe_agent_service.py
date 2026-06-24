from __future__ import annotations

import logging

from app.core.errors import LLMError, LLMUnavailableError, ValidationError
from app.db.session import get_session_factory
from app.llm.client import check_llm_available, get_llm_client
from app.models.user_profile import UserProfile
from app.schemas.agent_tools import (
    InventoryOnlyRecipeRequest,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
)
from app.services.inventory_service import InventoryService


logger = logging.getLogger(__name__)


def _build_profile_context(user_id: str) -> str:
    """从数据库读取用户档案，构建分类和偏好的上下文文本。"""
    parts: list[str] = []
    try:
        db = get_session_factory()()
        try:
            profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            if profile is None:
                return ""

            if profile.classification:
                label = "单身男性" if profile.classification == "single_male" else "单身女性"
                parts.append(f"用户分类：{label}")

            prefs = profile.preferences
            if isinstance(prefs, dict):
                dietary = prefs.get("dietary", [])
                if dietary:
                    parts.append(f"长期饮食偏好：{', '.join(dietary)}")
                lifestyle = prefs.get("lifestyle", [])
                if lifestyle:
                    parts.append(f"生活方式：{', '.join(lifestyle)}")
                cuisine = prefs.get("cuisine", [])
                if cuisine:
                    parts.append(f"偏好菜系：{', '.join(cuisine)}")
                equipment = prefs.get("equipment", [])
                if equipment:
                    parts.append(f"常用厨具：{', '.join(equipment)}")
                free_text = prefs.get("free_text", "")
                if free_text:
                    parts.append(f"用户补充：{free_text}")
        finally:
            db.close()
    except Exception:
        logger.debug("Could not fetch UserProfile for %s", user_id, exc_info=True)

    return "\n".join(parts)


class RecipeAgentService:
    def __init__(self, inventory_service: InventoryService | None = None) -> None:
        self._inventory_service = inventory_service or InventoryService()

    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        """仅通过 LLM 生成菜谱推荐。LLM 不可用时抛出 LLMUnavailableError。"""
        check_llm_available()
        return self._recommend_with_llm(payload)

    def _recommend_with_llm(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        profile_context = _build_profile_context(payload.user_id)

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名营养导向的菜谱规划助手。仅返回合法 JSON，字段必须是："
                    "title, rationale, estimated_calories, ingredients, steps, required_equipment, missing_ingredients。"
                    "所有文案使用中文，步骤简洁且可执行。"
                    ""
                    "ingredients 是数组，每个元素包含 name(食材名), amount(数量), unit(单位如 g/ml/个)。"
                    "例如: {\"name\": \"鸡胸肉\", \"amount\": 200, \"unit\": \"g\"}。"
                    ""
                    "请特别注意用户的分类（单身男性/女性）和长期饮食偏好，"
                    "为单身人士推荐分量适中、制作快捷的菜谱。"
                    ""
                    "要求："
                    "1. required_equipment 必须列出制作该菜谱所需全部厨具；"
                    "2. ingredients 必须列出所有主要食材及其用量；"
                    "3. steps 必须与 required_equipment 一致；"
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
                        {profile_context}
                        
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
            logger.warning("Recipe LLM generation failed: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

    # ---------- 仅使用库存材料生成菜谱 ----------

    def recommend_from_inventory_only(
        self, payload: InventoryOnlyRecipeRequest
    ) -> RecipeRecommendResponse:
        """获取真实库存，将库存作为 LLM 强制约束生成菜谱。

        库存为空时抛出 ValidationError；LLM 不可用时抛出 LLMUnavailableError。
        不允许使用模板或模拟结果。
        """
        check_llm_available()

        # 1. 获取当前用户的库存（按 user_id 过滤）
        all_items = self._inventory_service.list_items(user_id=payload.user_id)
        if not all_items:
            raise ValidationError("库存为空，无法仅使用库存材料生成菜谱。请先添加库存食材。")

        # 2. 构造库存清单文本
        inventory_lines: list[str] = []
        for item in all_items:
            inventory_lines.append(f"- {item.name}：{item.quantity} {item.unit}（过期日 {item.expire_date}）")

        inventory_text = "\n".join(inventory_lines)

        # 3. 构造 LLM 请求
        return self._recommend_with_inventory_constraint(payload, inventory_text)

    def _recommend_with_inventory_constraint(
        self,
        payload: InventoryOnlyRecipeRequest,
        inventory_text: str,
    ) -> RecipeRecommendResponse:
        profile_context = _build_profile_context(payload.user_id)

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名营养导向的菜谱规划助手。仅返回合法 JSON，字段必须是："
                    "title, rationale, estimated_calories, ingredients, steps, required_equipment, missing_ingredients。"
                    "所有文案使用中文，步骤简洁且可执行。"
                    ""
                    "ingredients 是数组，每个元素包含 name(食材名), amount(数量), unit(单位如 g/ml/个)。"
                    "例如: {\"name\": \"鸡胸肉\", \"amount\": 200, \"unit\": \"g\"}。"
                    ""
                    "【核心约束】"
                    "你必须仅使用下方「当前库存」中列出的食材来生成菜谱。"
                    "不得推荐任何未在库存清单中出现的食材。"
                    "如果库存中缺少制作该菜谱所必需的关键食材（例如想做番茄炒蛋但没有番茄），"
                    "仍需生成菜谱但必须在 missing_ingredients 字段中列出缺失的关键食材名称。"
                    "如果完全无法组合出任何合理的菜谱，请在 title 中写明「无法生成」，"
                    "在 rationale 中说明原因，ingredients 留空。"
                    ""
                    "请特别注意用户的分类（单身男性/女性）和长期饮食偏好，"
                    "为单身人士推荐分量适中、制作快捷的菜谱。"
                    ""
                    "要求："
                    "1. required_equipment 必须列出制作该菜谱所需全部厨具；"
                    "2. ingredients 中的食材名必须与库存清单中的食材名对应；"
                    "3. steps 必须与 required_equipment 一致；"
                    "4. 所有内容使用中文；"
                    "5. 步骤简洁且可执行。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"""用户ID：{payload.user_id}
                        餐食类型：{payload.meal_type}
                        目标热量：{payload.target_calories}
                        用户当前拥有厨具：{', '.join(payload.available_equipment) if payload.available_equipment else '无'}
                        饮食偏好：{', '.join(payload.dietary_preferences) if payload.dietary_preferences else '无'}
                        {profile_context}

                        【当前库存（仅可使用以下食材）】
                        {inventory_text}

                        请仅使用上述库存中的食材生成菜谱。
                        注意：
                        - 食材用量不得超过库存数量
                        - required_equipment 应列出制作该菜谱实际需要的全部厨具
                        - 如果库存不足以制作完整菜谱，请在 missing_ingredients 中列出缺少的关键食材
                    """
                ),
            },
        ]

        try:
            raw = get_llm_client().chat_json(messages, temperature=0.4, max_tokens=800)
            result = RecipeRecommendResponse.model_validate(raw)
            return result.model_copy(
                update={"estimated_calories": min(payload.target_calories, result.estimated_calories)}
            )
        except (LLMError, ValueError, TypeError) as exc:
            logger.warning("Inventory-only recipe LLM generation failed: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc
