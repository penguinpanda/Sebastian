"""Router Agent — A2A 兼容的全局意图路由。

识别用户意图 → 通过 InternalA2AClient 分发给子 Agent（A2A 协议）。
替代旧的 graph.py 硬编码 if/elif dispatch_agent。
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.a2a.client import InternalA2AClient
from app.a2a.schemas import AgentCard, Artifact, Message, Task
from app.agents.base import BaseAgent
from app.context.budget import ContextBudget
from app.core.errors import llm_unavailable_message
from app.llm.client import get_llm_client
from app.llm.output_parser import parse_router_response
from app.llm.prompts import build_router_messages, build_general_messages

logger = logging.getLogger(__name__)

# Intent → Agent 名称映射
INTENT_AGENT_MAP = {
    "recipe": "recipe",
    "health": "health",
    "inventory": "inventory",
    "search": "search",
    "equipment": "equipment",
    "general": None,  # 直接 LLM 回复
}


class RouterAgent(BaseAgent):
    """全局意图路由 Agent。

    流程:
    1. LLM 意图分类（recipe/health/inventory/search/equipment/general）
    2. 根据意图通过 InternalA2AClient 以 A2A 协议调子 Agent
    3. 收集子 Agent 产出，yield 给调用方
    """

    agent_card = AgentCard(
        name="Router Agent",
        description="意图识别与任务分发 — 分析用户消息，路由到最合适的子 Agent",
        url="http://localhost:8000/a2a",
    )

    def __init__(
        self,
        a2a_client: InternalA2AClient | None = None,
    ) -> None:
        super().__init__()
        self._a2a_client = a2a_client or InternalA2AClient()

    # ── 兼容旧接口 ──────────────────────────────────────────────

    def run(self, user_input: str, user_id: str | None = None) -> str:
        """旧同步接口兼容层（供 graph.py run_router_agent 使用）。"""
        import asyncio
        return asyncio.run(self.run_async(user_input, user_id))

    async def run_async(self, user_input: str, user_id: str | None = None) -> str:
        """异步执行路由器，返回最终回复文本。"""
        message = Message.from_text(user_input, metadata={"user_id": user_id or ""})
        task = self._task_manager.create_task(message=message)

        parts: list[str] = []
        async for artifact in self.handle_task(task, message):
            for part in artifact.parts:
                if hasattr(part, "text"):
                    parts.append(part.text)
        return "".join(parts)

    # ── A2A 接口 ────────────────────────────────────────────────

    async def execute(
        self,
        task: Task,
        message: Message,
        llm_messages: list[dict[str, str]],
        budget: ContextBudget,
    ) -> AsyncIterator[Artifact]:
        """A2A 异步处理入口：识别意图并路由到子 Agent。"""
        user_text = message.text
        user_id = message.metadata.get("user_id", "")

        if not user_text.strip():
            yield Artifact.from_text("请输入您的问题")
            return

        # 1. 意图分类
        intent, confidence = await self._classify_intent(user_text)
        budget.allocate("intent_classification", 150, f"intent={intent}")

        logger.info("Router intent: %s (confidence=%.2f)", intent, confidence)

        # 2. 根据意图分发
        agent_name = INTENT_AGENT_MAP.get(intent)

        if agent_name and agent_name in self._a2a_client.registered_agents:
            # 子 Agent 分发（A2A 协议）
            yield Artifact.from_text(
                f"正在转交给 {agent_name} Agent 处理...",
                metadata={"intent": intent, "action": "delegate"},
            )

            try:
                response = await self._a2a_client.send_task(
                    agent_name=agent_name,
                    message=message,
                    context_id=task.context_id,
                    blocking=True,
                    metadata={"intent": intent, "confidence": confidence},
                )

                if response.direct_reply:
                    yield Artifact.from_text(
                        response.direct_reply,
                        metadata={"agent": agent_name, "intent": intent},
                    )
                else:
                    for artifact in response.task.artifacts:
                        yield artifact

            except Exception as exc:
                logger.exception("Sub-agent '%s' dispatch failed", agent_name)
                yield Artifact.from_text(
                    f"{agent_name} Agent 暂时不可用: {exc}\n\n{await self._fallback_llm_reply(user_text, intent)}",
                    metadata={"error": True, "intent": intent},
                )
        else:
            # general 意图 → 直接 LLM 回复
            yield Artifact.from_text(
                await self._general_llm_reply(user_text),
                metadata={"intent": "general"},
            )

    # ── 意图分类 ────────────────────────────────────────────────

    async def _classify_intent(self, user_text: str) -> tuple[str, float]:
        """LLM 意图分类器。"""
        try:
            client = get_llm_client()
            messages = build_router_messages(user_text)
            raw = client.chat_json(messages, temperature=0.2, max_tokens=300)
            parsed = parse_router_response(raw)
            return parsed.intent, parsed.confidence
        except Exception as exc:
            logger.warning("Intent classification failed: %s", exc)
            return "general", 0.0

    # ── LLM 回复 ────────────────────────────────────────────────

    async def _fallback_llm_reply(self, user_text: str, intent: str) -> str:
        """子 Agent 不可用时的兜底 LLM 回复。"""
        prompt_map = {
            "recipe": "你是菜谱助手。根据用户需求推荐一道菜谱，用中文回复。简洁说明菜名、热量、主要食材和步骤。",
            "health": "你是健康分析助手。根据用户提供的信息给出健康建议，用中文回复。",
            "search": "你是知识搜索助手。回答用户问题，用中文回复，简洁准确。",
            "equipment": "你是厨具顾问。根据用户问题提供厨具建议，用中文回复。",
        }
        system = prompt_map.get(intent, "你是 Sebastian，一位个人 AI 生活助手。用中文简洁回复。")

        try:
            client = get_llm_client()
            return client.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user_text}],
                temperature=0.5,
                max_tokens=400,
            )
        except Exception:
            return llm_unavailable_message()

    async def _general_llm_reply(self, user_text: str) -> str:
        """通用闲聊 LLM 回复。"""
        try:
            client = get_llm_client()
            messages = build_general_messages(user_text)
            return client.chat(messages, temperature=0.5, max_tokens=400)
        except Exception:
            return llm_unavailable_message()
