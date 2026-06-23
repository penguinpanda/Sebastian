from __future__ import annotations

import hashlib
import logging
import re

from app.core.errors import LLMUnavailableError
from app.llm.client import check_llm_available, get_llm_client
from app.schemas.agent_tools import RecipeRecommendResponse, SearchAnswerRequest, SearchAnswerResponse
from app.schemas.search import MemoryCreateRequest
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


class SearchAgentService:
    def __init__(self, search_service: SearchService | None = None) -> None:
        self._search_service = search_service or SearchService()

    def answer(self, payload: SearchAnswerRequest) -> SearchAnswerResponse:
        """混合检索：ES 记忆库检索 + LLM 生成自然语言摘要。"""
        try:
            retrieval = self._search_service.search_memory(
                user_id=payload.user_id,
                query=payload.query,
                top_k=5,
                retrieval_mode="hybrid",
            )
        except Exception as exc:
            logger.warning("Search memory retrieval failed: %s", exc)
            raise LLMUnavailableError(f"记忆检索服务不可用: {exc}") from exc

        evidence = [item.content for item in retrieval.hits[:5]]
        if evidence:
            top = sorted(retrieval.hits[:5], key=lambda h: h.importance or 0, reverse=True)
            evidence = [item.content for item in top]

        summary = self._generate_summary_with_llm(
            query=payload.query, evidence=evidence,
        )

        return SearchAnswerResponse(
            summary=summary,
            evidence=evidence,
            retrieval_mode=retrieval.retrieval_mode,
        )

    @staticmethod
    def _generate_summary_with_llm(query: str, evidence: list[str]) -> str:
        """调用 LLM 将检索证据转化为自然语言摘要。"""
        check_llm_available()

        evidence_text = "\n".join(f"- {e}" for e in evidence) if evidence else "（无相关记忆证据）"

        messages = [
            {
                "role": "system",
                "content": (
                    "你是知识检索助手。根据用户的查询和检索到的记忆证据，"
                    "生成简洁准确的摘要回答。用中文回复，150字以内。"
                    "如果有证据则基于证据回答，如果没有证据则如实说明。"
                ),
            },
            {
                "role": "user",
                "content": f"用户查询：{query}\n\n检索到的记忆证据：\n{evidence_text}\n\n请生成摘要回答。",
            },
        ]

        try:
            return get_llm_client().chat(messages, temperature=0.3, max_tokens=300)
        except Exception as exc:
            logger.warning("Search summary LLM generation failed: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

    def search_recipes(
        self, user_id: str, query: str, top_k: int = 5,
    ) -> list[dict]:
        """从菜谱库检索匹配 query 的菜谱，返回 {title, calories, ingredients, times_made}。"""
        from sqlalchemy import select
        from app.db.session import get_session_factory
        from app.models.recipe import Recipe

        try:
            db = next(get_session_factory()())
            stmt = (
                select(Recipe)
                .where(Recipe.user_id == user_id)
                .where(Recipe.title.ilike(f"%{query}%"))
                .order_by(Recipe.times_made.desc())
                .limit(top_k)
            )
            rows = db.execute(stmt).scalars().all()
            return [
                {
                    "title": r.title,
                    "calories": r.estimated_calories,
                    "ingredients": [i.get("name", "") for i in (r.ingredients or [])],
                    "steps": r.steps or [],
                    "times_made": r.times_made,
                }
                for r in rows
            ]
        except Exception:
            return []

    def save_recipe_memory(
        self, user_id: str, recipe: RecipeRecommendResponse
    ) -> tuple[str, bool]:
        """将菜谱保存为记忆，自动去重：同名+同配料视为重复。

        返回 (memory_id, is_duplicate)。
        """
        # 生成菜谱指纹
        content = f"{recipe.title}|{'|'.join(sorted(i.name for i in recipe.ingredients))}"
        recipe_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # 检查是否已有相似菜谱
        try:
            existing = self._search_service.search_memory(
                user_id=user_id,
                query=recipe.title,
                top_k=5,
                retrieval_mode="lexical",
            )
            for hit in existing.hits:
                if self._recipe_similarity(recipe, hit.content) > 0.85:
                    return (hit.memory_id, True)
        except Exception:
            pass

        memory_text = (
            f"【菜谱】{recipe.title}（约{recipe.estimated_calories}kcal）\n"
            f"配料：{'、'.join(f'{i.name}{i.amount}{i.unit}' for i in recipe.ingredients)}\n"
            f"步骤：{'；'.join(recipe.steps[:3])}"
        )
        memory_id, _, _ = self._search_service.index_memory(
            MemoryCreateRequest(
                user_id=user_id,
                memory_type="recipe",
                content=memory_text,
                tags=["recipe", recipe.title] + [i.name for i in recipe.ingredients[:5]],
                importance=7,
            )
        )
        return (memory_id, False)

    @staticmethod
    def _recipe_similarity(recipe: RecipeRecommendResponse, existing_content: str) -> float:
        """菜谱相似度：基于标题+配料的重叠度简单计算（0~1）。"""
        if recipe.title and recipe.title in existing_content:
            return 0.9
        ingredient_names = {i.name for i in recipe.ingredients}
        if not ingredient_names:
            return 0.0
        matches = sum(1 for name in ingredient_names if name in existing_content)
        return matches / len(ingredient_names)

