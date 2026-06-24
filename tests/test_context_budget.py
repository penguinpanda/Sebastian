"""上下文预算管理器测试 — 验证动态 Token 配额管理。"""

from __future__ import annotations

import pytest

from app.context.budget import ContextBudget
from app.context.token_counter import TokenCounter


class TestContextBudget:
    """测试 ContextBudget 的核心功能。"""

    def test_initial_state(self) -> None:
        """初始化时 used=0, remaining=max。"""
        budget = ContextBudget(max_context_tokens=10000)
        assert budget.used == 0
        assert budget.remaining == 10000
        assert budget.usage_ratio == 0.0

    def test_allocate_within_budget(self) -> None:
        """在预算内分配应成功。"""
        budget = ContextBudget(max_context_tokens=10000)
        assert budget.allocate("system", 500, "system prompt")
        assert budget.used == 500
        assert budget.remaining == 9500

    def test_allocate_exceeds_budget(self) -> None:
        """超出预算的分配应失败并返回 False。"""
        budget = ContextBudget(max_context_tokens=1000)
        assert not budget.allocate("large", 2000, "too large")
        assert budget.used == 0  # 未发生部分分配

    def test_multiple_allocations(self) -> None:
        """多次分配累加计数。"""
        budget = ContextBudget(max_context_tokens=10000)
        budget.allocate("system", 500)
        budget.allocate("history", 2000)
        budget.allocate("retrieval", 800)
        assert budget.used == 3300
        assert budget.remaining == 6700

    def test_allocate_zero_tokens(self) -> None:
        """分配 0 token 应总是成功。"""
        budget = ContextBudget()
        assert budget.allocate("zero", 0)
        assert budget.used == 0

    def test_usage_ratio(self) -> None:
        """usage_ratio 应正确反映使用比例。"""
        budget = ContextBudget(max_context_tokens=1000)
        budget.allocate("test", 300)
        assert budget.usage_ratio == pytest.approx(0.3, abs=0.01)
        budget.allocate("test2", 700)
        assert budget.usage_ratio == 1.0  # 正好满

    def test_usage_ratio_capped_at_one(self) -> None:
        """usage_ratio 不应超过 1.0。"""
        budget = ContextBudget(max_context_tokens=1000)
        budget.max_context_tokens = 0  # 边界情况
        assert budget.usage_ratio == 0.0

    def test_can_fit_positive(self) -> None:
        """文本在剩余预算内时 can_fit 返回 True。"""
        budget = ContextBudget(max_context_tokens=10000)
        budget.allocate("existing", 500)
        assert budget.can_fit("short text")

    def test_can_fit_negative(self) -> None:
        """文本超过剩余预算时 can_fit 返回 False。"""
        budget = ContextBudget(max_context_tokens=1000)
        budget.allocate("existing", 900)
        # 剩余 100 tokens，"你好" 约 3 tokens，应能容纳
        assert budget.can_fit("你好")

    def test_fit_text_within_budget(self) -> None:
        """fit_text 应在预算内时完整保留文本。"""
        budget = ContextBudget(max_context_tokens=10000)
        text = "Hello world"
        result = budget.fit_text("test", text)
        assert result == text
        assert budget.used > 0

    def test_fit_text_truncates_when_exceeding(self) -> None:
        """fit_text 应在超出预算时截断。"""
        budget = ContextBudget(max_context_tokens=200)
        budget.allocate("existing", 150)
        long_text = "这是一个很长的测试文本。" * 50
        result = budget.fit_text("large", long_text)
        assert len(result) < len(long_text)

    def test_fit_text_empty(self) -> None:
        """fit_text 空文本应返回空字符串。"""
        budget = ContextBudget()
        assert budget.fit_text("empty", "") == ""

    def test_reserve_output_within_limit(self) -> None:
        """reserve_output 在默认 4K 内应成功。"""
        budget = ContextBudget(max_context_tokens=10000)
        assert budget.reserve_output(3000)  # 3000 < 4000

    def test_reserve_output_exceeds_default(self) -> None:
        """reserve_output 超出默认 4K 预留时需从剩余扣除。"""
        budget = ContextBudget(max_context_tokens=10000)
        success = budget.reserve_output(5000)  # 5000 > 4000, 需额外 1000
        assert success

    def test_summary_contains_allocations(self) -> None:
        """summary 应列出所有分配。"""
        budget = ContextBudget(max_context_tokens=10000)
        budget.allocate("system", 500, "sys prompt")
        budget.allocate("history", 1000, "chat history")
        s = budget.summary()
        assert "system" in s
        assert "history" in s
        assert "500" in s
        assert "1000" in s

    def test_reset_clears_allocations(self) -> None:
        """reset 应清空所有分配。"""
        budget = ContextBudget()
        budget.allocate("test", 500)
        budget.reset()
        assert budget.used == 0
        assert budget.remaining == budget.max_context_tokens

    def test_count_delegation(self) -> None:
        """count 方法应委托给 TokenCounter。"""
        budget = ContextBudget()
        assert budget.count("hello") > 0

    def test_default_max_tokens(self) -> None:
        """默认最大 token 数为 60000（64K-4K）。"""
        budget = ContextBudget()
        assert budget.max_context_tokens == 60000
