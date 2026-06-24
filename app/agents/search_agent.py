"""Search Agent — A2A 兼容的搜索助手。

混合检索 ES 记忆库并用 LLM 生成自然语言摘要。
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.a2a.schemas import AgentCard, Artifact, Message, Task
from app.agents.base import BaseAgent
from app.context.budget import ContextBudget
from app.services.search_agent_service import SearchAgentService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """知识搜索 Agent。

    流程: ES 混合检索 → Token 预算截断 → LLM 摘要生成。
    """

    agent_card = AgentCard(
        name="Search Agent",
        description="知识搜索助手 — 检索记忆库并用 LLM 生成自然语言摘要",
        url="http://localhost:8000/a2a",
    )

    def __init__(
        self,
        service: SearchAgentService | None = None,
        search_service: SearchService | None = None,
    ) -> None:
        super().__init__()
        self._service = service or SearchAgentService(search_service=search_service)

    # ── 兼容旧接口 ──────────────────────────────────────────────

    def answer(self, payload):
        """旧同步接口兼容层。"""
        from app.orchestration.agent_graphs import run_search_agent
        return run_search_agent(payload, service=self._service)

    # ── A2A 接口 ────────────────────────────────────────────────

    async def execute(
        self,
        task: Task,
        message: Message,
        llm_messages: list[dict[str, str]],
        budget: ContextBudget,
    ) -> AsyncIterator[Artifact]:
        """A2A 异步处理入口。"""
        user_text = message.text
        user_id = message.metadata.get("user_id", "default")

        # ES 检索
        try:
            retrieval = self._service._search_service.search_memory(
                user_id=user_id,
                query=user_text,
                top_k=5,
                retrieval_mode="hybrid",
            )
        except Exception as exc:
            logger.warning("Search memory retrieval failed: %s", exc)
            yield Artifact.from_text(f"记忆检索服务不可用: {exc}", metadata={"error": True})
            return

        evidence = [item.content for item in retrieval.hits[:5]]
        if evidence:
            top = sorted(retrieval.hits[:5], key=lambda h: h.importance or 0, reverse=True)
            evidence = [item.content for item in top]

        # Token 预算内压缩检索结果
        retrieval_budget = budget.remaining
        if retrieval_budget < 100:
            logger.warning("Not enough budget for retrieval: %d tokens remaining", retrieval_budget)
            truncated_evidence = ""
        else:
            from app.context.compressor import ContextCompressor
            compressor = ContextCompressor(self._token_counter)
            truncated_evidence = compressor.compress_retrieval(
                evidence,
                budget_tokens=min(retrieval_budget, 800),
            )
            budget.allocate("retrieval", self._token_counter.count(truncated_evidence), truncated_evidence)

        # LLM 摘要
        try:
            summary = self._service._generate_summary_with_llm(
                query=user_text, evidence=evidence,
            )
        except Exception as exc:
            logger.warning("Search summary LLM failed: %s", exc)
            summary = f"检索到 {len(evidence)} 条相关记忆，但摘要生成失败: {exc}"

        yield Artifact.from_text(
            summary,
            metadata={
                "retrieval_mode": retrieval.retrieval_mode,
                "evidence_count": len(evidence),
            },
        )

    async def get_retrieved_context(self, message: Message, budget: ContextBudget) -> str:
        """预检索并返回记忆上下文，供 BaseAgent.build_prompt 使用。"""
        user_text = message.text
        user_id = message.metadata.get("user_id", "default")

        try:
            retrieval = self._service._search_service.search_memory(
                user_id=user_id,
                query=user_text,
                top_k=3,
                retrieval_mode="hybrid",
            )
            evidence = [item.content for item in retrieval.hits[:3]]
            if not evidence:
                return ""

            from app.context.compressor import ContextCompressor
            compressor = ContextCompressor(self._token_counter)
            return compressor.compress_retrieval(evidence, budget_tokens=min(budget.remaining, 500))
        except Exception:
            return ""
