"""Token 计数器 — 基于 tiktoken 的精确 Token 管理。

deepseek-chat 模型使用 o200k_base 编码（与 gpt-4o 兼容）。
"""

from __future__ import annotations

import logging
from functools import lru_cache

import tiktoken

logger = logging.getLogger(__name__)

# deepseek-chat 兼容的编码器名称
_DEEPSEEK_ENCODING = "o200k_base"


@lru_cache(maxsize=1)
def _get_encoding():
    """懒加载 tiktoken 编码器，进程内缓存一份。"""
    try:
        return tiktoken.get_encoding(_DEEPSEEK_ENCODING)
    except Exception:
        logger.warning(
            "tiktoken encoding '%s' not found, falling back to cl100k_base",
            _DEEPSEEK_ENCODING,
        )
        return tiktoken.get_encoding("cl100k_base")


class TokenCounter:
    """精确 Token 计数器，基于 tiktoken。"""

    # 每条消息的角色/格式开销（经验值）
    MESSAGE_OVERHEAD_TOKENS = 4  # role + content 标记

    def __init__(self, model: str = "deepseek-chat") -> None:
        self._model = model
        self._encoding = _get_encoding()

    def count(self, text: str) -> int:
        """计算单段文本的 token 数。"""
        if not text:
            return 0
        return len(self._encoding.encode(text))

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """计算消息列表的总 token 数（含角色开销）。"""
        total = 0
        for msg in messages:
            total += self.MESSAGE_OVERHEAD_TOKENS
            for key in ("content", "text"):
                if text := msg.get(key):
                    total += self.count(str(text))
        return total

    def estimate_tokens(self, text: str) -> int:
        """快速字符估算（兜底方案：中文约 1.5 字符/token，英文约 4 字符/token）。

        当 tiktoken 不可用时使用此方法。
        """
        if not text:
            return 0
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    @property
    def encoding_name(self) -> str:
        return self._encoding.name

    @property
    def model(self) -> str:
        return self._model


# 进程级单例
@lru_cache(maxsize=1)
def get_token_counter(model: str = "deepseek-chat") -> TokenCounter:
    return TokenCounter(model=model)
