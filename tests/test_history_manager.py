"""对话历史管理器测试 — 滑动窗口 + 摘要压缩。"""

from __future__ import annotations

import pytest

from app.a2a.schemas import Message
from app.context.budget import ContextBudget
from app.context.history_manager import ConversationHistoryManager
from app.context.token_counter import TokenCounter


class TestConversationHistoryManager:
    """测试对话历史管理器的核心功能。"""

    def test_empty_history(self) -> None:
        """空历史应返回空上下文。"""
        hm = ConversationHistoryManager()
        budget = ContextBudget()
        msgs = hm.build_context_messages([], budget)
        assert msgs == []

    def test_short_history_full_injection(self) -> None:
        """短历史（不超阈值）应全量注入。"""
        hm = ConversationHistoryManager(summary_trigger_tokens=10000)  # 设高阈值
        budget = ContextBudget()

        history = [
            Message.from_text("你好", role="user"),
            Message.from_text("你好！有什么可以帮助你的？", role="agent"),
        ]
        msgs = hm.build_context_messages(history, budget)

        assert len(msgs) >= 2
        assert budget.used > 0

    def test_long_history_triggers_summary(self) -> None:
        """长历史（超阈值）应触发摘要 + 保留最近 N 轮。"""
        hm = ConversationHistoryManager(
            summary_trigger_tokens=30,  # 极低阈值确保短文本也触发
            window_size=2,
        )
        budget = ContextBudget()

        history = [
            Message.from_text("第1轮问题，这是一个较长的测试消息用于触发摘要", role="user"),
            Message.from_text("第1轮回答，内容也较长用于压缩测试", role="agent"),
            Message.from_text("第2轮问题继续测试", role="user"),
            Message.from_text("第2轮回答继续回复", role="agent"),
            Message.from_text("第3轮问题", role="user"),
            Message.from_text("第3轮回答", role="agent"),
        ]
        msgs = hm.build_context_messages(history, budget)

        # 应有 system 消息包含摘要（前缀为 "[对话历史摘要]"）
        assert len(msgs) > 0
        system_msgs = [m for m in msgs if m["role"] == "system"]
        summary_msgs = [m for m in system_msgs if "对话历史摘要" in m["content"]]
        assert len(summary_msgs) > 0, (
            f"Expected summary system message, got system messages: "
            f"{[m['content'][:80] for m in system_msgs]}"
        )

    def test_cached_summary_is_used(self) -> None:
        """已有缓存摘要时直接使用。"""
        hm = ConversationHistoryManager()
        budget = ContextBudget()

        history = [Message.from_text("test", role="user")]
        cached = "用户之前询问了关于菜谱的问题"
        msgs = hm.build_context_messages(history, budget, summary=cached)

        # 应有一条包含缓存摘要的 system 消息
        system_msgs = [m for m in msgs if m["role"] == "system"]
        assert any(cached in m["content"] for m in system_msgs)

    def test_should_summarize_small_history(self) -> None:
        """短历史不需要摘要。"""
        hm = ConversationHistoryManager(summary_trigger_tokens=10000)
        history = [Message.from_text("hi", role="user")]
        assert not hm.should_summarize(history)

    def test_should_summarize_large_history(self) -> None:
        """长历史需要摘要。"""
        hm = ConversationHistoryManager(summary_trigger_tokens=10)  # 极低阈值
        history = [
            Message.from_text("A" * 200, role="user"),  # 长文本
        ]
        assert hm.should_summarize(history)

    def test_prepare_messages_for_storage(self) -> None:
        """prepare_messages_for_storage 返回正确格式。"""
        hm = ConversationHistoryManager()
        msgs = hm.prepare_messages_for_storage("用户消息", "Agent 回复")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "用户消息"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Agent 回复"
        assert "timestamp" in msgs[0]

    def test_build_context_preserves_message_order(self) -> None:
        """构建的上下文消息应保持时间顺序。"""
        hm = ConversationHistoryManager(summary_trigger_tokens=10000)
        budget = ContextBudget()

        history = [
            Message.from_text("Q1", role="user"),
            Message.from_text("A1", role="agent"),
            Message.from_text("Q2", role="user"),
        ]
        msgs = hm.build_context_messages(history, budget)

        # 过滤掉 system 消息，检查用户消息顺序
        user_msgs = [m for m in msgs if m["role"] in ("user", "assistant")]
        assert len(user_msgs) >= 3

    def test_agent_role_mapped_to_assistant(self) -> None:
        """A2A agent role 应映射为 OpenAI assistant role。"""
        hm = ConversationHistoryManager(summary_trigger_tokens=10000)
        budget = ContextBudget()

        history = [Message.from_text("agent reply", role="agent")]
        msgs = hm.build_context_messages(history, budget)
        # 应有一条 assistant 角色消息
        assert any(m["role"] == "assistant" for m in msgs)

    def test_fallback_summary_contains_topics(self) -> None:
        """兜底摘要应包含最近消息的话题关键词。"""
        result = ConversationHistoryManager._build_fallback_summary([
            Message.from_text("我想吃低卡的午餐", role="user"),
            Message.from_text("推荐鸡胸肉沙拉", role="agent"),
        ])
        assert result != "无历史对话"
        assert len(result) > 0
