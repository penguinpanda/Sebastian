"""上下文压缩器 — LLM 摘要 + 动态截断。

提供两类压缩:
1. summarize_history: 将历史对话压缩为 ≤200 tokens 的摘要
2. compress_retrieval: 动态截断检索结果以适应当前 token 预算
"""

from __future__ import annotations

import logging

from app.context.token_counter import TokenCounter
from app.llm.client import get_llm_client

logger = logging.getLogger(__name__)


class ContextCompressor:
    """使用 LLM 对上下文进行摘要压缩。"""

    def __init__(self, token_counter: TokenCounter | None = None) -> None:
        self._token_counter = token_counter or TokenCounter()

    async def summarize_history(
        self,
        messages: list[dict[str, str]],
        max_summary_tokens: int = 200,
    ) -> str:
        """将历史对话压缩为简短摘要。

        Args:
            messages: 历史消息列表（role/content 格式）
            max_summary_tokens: 摘要最大 token 数

        Returns:
            摘要文本
        """
        if not messages:
            return ""

        # 构建对话文本
        dialogue = []
        for msg in messages:
            role = "用户" if msg.get("role") == "user" else "助手"
            dialogue.append(f"{role}: {msg.get('content', '')}")

        dialogue_text = "\n".join(dialogue)

        # 如果对话很短，不需要压缩
        if self._token_counter.count(dialogue_text) <= max_summary_tokens * 2:
            return dialogue_text

        # LLM 摘要
        prompt = (
            "请将以下对话历史总结为简洁的摘要（中文，200字以内），"
            "保留关键信息：用户需求、讨论主题、重要结论。\n\n"
            f"{dialogue_text}"
        )

        try:
            client = get_llm_client()
            summary = client.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_summary_tokens * 2,  # 中文约 1.5 字符/token
            )
            return summary.strip()
        except Exception as exc:
            logger.warning("History summarization failed: %s", exc)
            # 兜底：取最近几条消息的关键词
            return self._fallback_summary(messages)

    def compress_retrieval(
        self,
        memories: list[str],
        budget_tokens: int,
        *,
        sort_by_importance: bool = True,
    ) -> str:
        """动态截断检索结果以适应当前 token 预算。

        Args:
            memories: 检索到的记忆文本列表
            budget_tokens: 分配给检索结果的 token 预算
            sort_by_importance: 是否按重要性排序（需在调用前排序）

        Returns:
            截断后的拼接文本
        """
        if not memories:
            return ""

        result_parts: list[str] = []
        used = 0

        for memory in memories:
            mem_tokens = self._token_counter.count(memory)
            if used + mem_tokens <= budget_tokens:
                result_parts.append(f"- {memory}")
                used += mem_tokens
            else:
                # 尝试截断当前记忆以填入剩余空间
                remaining = budget_tokens - used
                if remaining > 20:  # 至少 20 tokens 才有意义
                    encoding = self._token_counter._encoding
                    truncated_tokens = encoding.encode(memory)[:remaining]
                    truncated = encoding.decode(truncated_tokens) + "..."
                    result_parts.append(f"- {truncated}")
                break

        if not result_parts:
            return "（检索结果超出上下文限制，已省略）"

        return "\n".join(result_parts)

    @staticmethod
    def _fallback_summary(messages: list[dict[str, str]]) -> str:
        """LLM 不可用时的兜底摘要。"""
        topics = []
        for msg in messages[-5:]:
            text = msg.get("content", "")[:40]
            if text:
                topics.append(text)
        return "；".join(topics) if topics else "无历史对话"
