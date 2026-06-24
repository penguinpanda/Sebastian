"""Token 计数器测试 — 验证 tiktoken 精确计数和兜底估算。"""

from __future__ import annotations

import pytest

from app.context.token_counter import TokenCounter, get_token_counter


class TestTokenCounter:
    """测试 TokenCounter 类的核心功能。"""

    def test_singleton_returns_same_instance(self) -> None:
        """get_token_counter() 应返回全局单例。"""
        tc1 = get_token_counter()
        tc2 = get_token_counter()
        assert tc1 is tc2

    def test_count_empty_string(self) -> None:
        """空字符串 token 数为 0。"""
        tc = TokenCounter()
        assert tc.count("") == 0
        assert tc.count("  ") >= 0

    def test_count_english_text(self) -> None:
        """英文文本 token 数应在合理范围。"""
        tc = TokenCounter()
        text = "Hello, world! This is a test."
        tokens = tc.count(text)
        assert tokens > 0
        assert tokens < 50  # 13 个英文字符，token 数不应超过 50

    def test_count_chinese_text(self) -> None:
        """中文文本 token 数应在合理范围。"""
        tc = TokenCounter()
        text = "你好世界，这是一个测试。"
        tokens = tc.count(text)
        assert tokens > 0
        assert tokens < 30  # 12 个中文字符

    def test_count_mixed_text(self) -> None:
        """中英混合文本。"""
        tc = TokenCounter()
        text = "Sebastian 是一个 AI 助手系统，支持 health 和 recipe 功能。"
        tokens = tc.count(text)
        assert tokens > 0
        assert tokens < 80

    def test_count_messages_with_overhead(self) -> None:
        """count_messages 应包含每条消息的格式开销。"""
        tc = TokenCounter()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ]
        total = tc.count_messages(messages)
        individual = sum(tc.count(m["content"]) for m in messages)
        # 总 token 数应大于纯内容 token 之和（因为含角色开销）
        assert total > individual

    def test_count_messages_empty_list(self) -> None:
        """空消息列表 token 数为 0。"""
        tc = TokenCounter()
        assert tc.count_messages([]) == 0

    def test_estimate_tokens_rough_approximation(self) -> None:
        """estimate_tokens 应返回大致合理的中文字符估算。"""
        tc = TokenCounter()
        text = "你好世界"  # 4 个中文字符
        estimated = tc.estimate_tokens(text)
        assert estimated >= 2  # 4/1.5 = 2.67
        assert estimated <= 6

    def test_estimate_tokens_english(self) -> None:
        """estimate_tokens 对英文应有合理估算。"""
        tc = TokenCounter()
        text = "hello world test"  # 15 个字符（含空格）
        estimated = tc.estimate_tokens(text)
        assert estimated >= 2   # 15/4 = 3.75
        assert estimated <= 6

    def test_encoding_name_is_known(self) -> None:
        """编码器名称应为已知值。"""
        tc = TokenCounter()
        assert tc.encoding_name in ("o200k_base", "cl100k_base")

    def test_model_property(self) -> None:
        """model 属性应反映初始化参数。"""
        tc = TokenCounter(model="deepseek-chat")
        assert tc.model == "deepseek-chat"

    def test_count_long_text_performance(self) -> None:
        """长文本计数应在合理时间内完成。"""
        tc = TokenCounter()
        text = "这是一个测试句子。" * 500  # ~5000 中文字符
        tokens = tc.count(text)
        assert tokens > 0
        assert tokens < 10000

    def test_count_messages_with_different_keys(self) -> None:
        """消息字典可能有 text 或 content 键。"""
        tc = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "text": "Hi there!"},
            {"role": "user", "content": ""},  # 空内容
        ]
        total = tc.count_messages(messages)
        assert total > 0

    def test_count_is_monotonic(self) -> None:
        """较长的文本应有更多的 token。"""
        tc = TokenCounter()
        short = "你好"
        long = "你好世界，这是一个很长的测试文本，用来验证 token 计数器的单调性。"
        assert tc.count(short) < tc.count(long)
