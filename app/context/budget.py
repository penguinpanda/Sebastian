"""上下文预算管理器 — 动态管理 LLM 上下文窗口的 Token 配额。

deepseek-chat 上下文窗口为 64K tokens。
策略：留 4K 给输出，60K 用于输入上下文。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.context.token_counter import TokenCounter

logger = logging.getLogger(__name__)

# 上下文窗口配置
MAX_CONTEXT_TOKENS = 60000   # 输入上下文上限（64K - 4K 输出预留）
RESERVED_OUTPUT = 4000       # 输出 token 预留
MAX_INPUT_TOKENS = 64000     # 模型总上下文窗口


@dataclass
class BudgetAllocation:
    """单次分配的记录。"""
    component: str
    tokens: int
    text_preview: str = ""


@dataclass
class ContextBudget:
    """动态上下文预算管理器。

    追踪各组件（system prompt、检索记忆、对话历史、当前消息）的 token 消耗，
    确保总输入不超过 MAX_CONTEXT_TOKENS。

    用法:
        budget = ContextBudget()
        budget.allocate("system", tokens)  # 申请配额
        if budget.can_fit(some_text):      # 检查能否容纳
            budget.allocate("retrieval", budget.count(some_text))
    """

    max_context_tokens: int = MAX_CONTEXT_TOKENS
    token_counter: TokenCounter = field(default_factory=lambda: TokenCounter())

    def __post_init__(self):
        self._allocations: list[BudgetAllocation] = []

    # ── 查询 ────────────────────────────────────────────────────

    @property
    def used(self) -> int:
        """已使用的 token 数。"""
        return sum(a.tokens for a in self._allocations)

    @property
    def remaining(self) -> int:
        """剩余可用 token 数。"""
        return max(0, self.max_context_tokens - self.used)

    @property
    def usage_ratio(self) -> float:
        """已用比例（0-1）。"""
        if self.max_context_tokens <= 0:
            return 0.0
        return min(1.0, self.used / self.max_context_tokens)

    def can_fit(self, text: str) -> bool:
        """检查文本能否放入当前预算。"""
        return self.token_counter.count(text) <= self.remaining

    def count(self, text: str) -> int:
        """计算文本的 token 数。"""
        return self.token_counter.count(text)

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """计算消息列表的 token 数。"""
        return self.token_counter.count_messages(messages)

    # ── 分配 ────────────────────────────────────────────────────

    def allocate(self, component: str, tokens: int, text_preview: str = "") -> bool:
        """为组件分配 token 配额。

        返回 True 表示分配成功，False 表示配额不足（不会部分分配）。
        """
        if tokens <= 0:
            return True

        if self.used + tokens > self.max_context_tokens:
            logger.warning(
                "Budget exceeded: component=%s requested=%d used=%d remaining=%d",
                component, tokens, self.used, self.remaining,
            )
            return False

        self._allocations.append(BudgetAllocation(
            component=component,
            tokens=tokens,
            text_preview=text_preview[:100],
        ))
        return True

    def fit_text(self, component: str, text: str, max_tokens: int | None = None) -> str:
        """尝试将文本适配到剩余预算，超出部分截断。

        返回截断后的文本（可能需要截断）。
        """
        if not text:
            return text

        text_tokens = self.count(text)
        limit = min(max_tokens or text_tokens, self.remaining)

        if text_tokens <= limit:
            self.allocate(component, text_tokens, text)
            return text

        # 需要截断：按 token 数截取
        encoding = self.token_counter._encoding
        truncated_tokens = encoding.encode(text)[:limit]
        truncated = encoding.decode(truncated_tokens)
        actual_tokens = len(truncated_tokens)
        self.allocate(component, actual_tokens, truncated)
        logger.info("Truncated '%s': %d → %d tokens", component, text_tokens, actual_tokens)
        return truncated

    def reserve_output(self, max_tokens: int) -> bool:
        """为输出预留空间（从剩余预算中扣除）。"""
        if max_tokens <= RESERVED_OUTPUT:
            return True
        extra = max_tokens - RESERVED_OUTPUT
        if extra <= self.remaining:
            self._allocations.append(BudgetAllocation(
                component="output_reserve",
                tokens=extra,
            ))
            return True
        return False

    # ── 报告 ────────────────────────────────────────────────────

    def summary(self) -> str:
        """生成预算使用摘要。"""
        lines = [f"Context Budget: {self.used}/{self.max_context_tokens} tokens ({self.usage_ratio:.0%})"]
        for a in self._allocations:
            pct = f"{a.tokens / self.max_context_tokens * 100:.1f}%"
            preview = f" | {a.text_preview}" if a.text_preview else ""
            lines.append(f"  [{a.component}] {a.tokens} tokens ({pct}){preview}")
        if self.remaining > 0:
            lines.append(f"  [remaining] {self.remaining} tokens")
        return "\n".join(lines)

    def reset(self) -> None:
        """重置预算（用于新一轮对话）。"""
        self._allocations.clear()
