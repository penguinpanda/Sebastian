"""对话历史管理器 — 滑动窗口 + LLM 摘要压缩。

策略:
- 最近 SLIDING_WINDOW_SIZE 轮对话保留原文
- 总 token 数超过 SUMMARY_TRIGGER_TOKENS 时，更早的轮次由 LLM 摘要压缩
- 摘要缓存到 PostgreSQL conversations 表的 summary 字段
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from app.a2a.schemas import Message
from app.context.budget import ContextBudget
from app.context.token_counter import TokenCounter


logger = logging.getLogger(__name__)

# 滑动窗口配置
SLIDING_WINDOW_SIZE = 10        # 保留最近 N 轮原文
SUMMARY_TRIGGER_TOKENS = 4000   # 总 token 超此阈值触发摘要
SUMMARY_MAX_TOKENS = 800         # 摘要最大 token 数


class ConversationHistoryManager:
    """多轮对话历史管理器。

    功能:
    1. 从 PG conversations 表加载历史
    2. 滑动窗口：最近 N 轮保留原文，更早的由 LLM 摘要
    3. 摘要缓存（PG summary 字段）
    4. 新轮次保存 + 触发摘要检查
    """

    def __init__(
        self,
        token_counter: TokenCounter | None = None,
        window_size: int = SLIDING_WINDOW_SIZE,
        summary_trigger_tokens: int = SUMMARY_TRIGGER_TOKENS,
        summary_max_tokens: int = SUMMARY_MAX_TOKENS,
    ) -> None:
        self._token_counter = token_counter or TokenCounter()
        self._window_size = window_size
        self._summary_trigger_tokens = summary_trigger_tokens
        self._summary_max_tokens = summary_max_tokens

    # ── 加载上下文 ─────────────────────────────────────────────

    def build_context_messages(
        self,
        history: list[Message],
        budget: ContextBudget,
        *,
        summary: str = "",
    ) -> list[dict[str, str]]:
        """从历史 Message 列表构建 LLM 上下文消息列表。

        Args:
            history: 完整对话历史 Message 列表
            budget: 上下文预算管理器
            summary: 已有的历史摘要（从 DB 缓存加载）

        Returns:
            适合注入 LLM 的 messages 列表
        """
        if not history and not summary:
            return []

        total_tokens = sum(self._token_counter.count(m.text) for m in history)

        # 判断是否需要摘要压缩
        need_summary = total_tokens > self._summary_trigger_tokens or summary
        context: list[dict[str, str]] = []

        if need_summary:
            # 只保留最近 window_size 轮原文
            recent = history[-self._window_size:] if len(history) > self._window_size else history
            older = history[:-self._window_size] if len(history) > self._window_size else []

            # 构建摘要上下文
            summary_text = summary or self._build_fallback_summary(older)
            summary_tokens = self._token_counter.count(summary_text)
            budget.allocate("history_summary", min(summary_tokens, self._summary_max_tokens), summary_text)
            context.append({
                "role": "system",
                "content": f"[对话历史摘要] {summary_text}",
            })

            # 注入最近原文
            for msg in recent:
                role = "assistant" if msg.role == "agent" else msg.role
                text = msg.text
                text_tokens = self._token_counter.count(text)
                budget.allocate(f"history_{role}", text_tokens, text)
                context.append({"role": role, "content": text})
        else:
            # 全量注入
            for msg in history:
                role = "assistant" if msg.role == "agent" else msg.role
                text = msg.text
                text_tokens = self._token_counter.count(text)
                budget.allocate(f"history_{role}", text_tokens, text)
                context.append({"role": role, "content": text})

        return context

    # ── 摘要生成 ───────────────────────────────────────────────

    def should_summarize(self, history: list[Message]) -> bool:
        """判断是否需要生成摘要。"""
        total_tokens = sum(self._token_counter.count(m.text) for m in history)
        return total_tokens > self._summary_trigger_tokens

    @staticmethod
    def _build_fallback_summary(messages: list[Message]) -> str:
        """无 LLM 时的兜底摘要：拼接最近话题关键词。"""
        if not messages:
            return "无历史对话"
        topics = []
        for msg in messages[-5:]:  # 最近 5 条提取主题
            text = msg.text[:50]
            topics.append(text)
        return "；".join(topics)

    # ── 保存 ───────────────────────────────────────────────────

    def prepare_messages_for_storage(
        self,
        user_message: str,
        agent_reply: str,
    ) -> list[dict[str, Any]]:
        """将一轮对话转换为存储格式。"""
        now = datetime.now(timezone.utc).isoformat()
        return [
            {"role": "user", "content": user_message, "timestamp": now},
            {"role": "assistant", "content": agent_reply, "timestamp": now},
        ]
