"""Prompt templates for each agent intent."""
from __future__ import annotations

SYSTEM_INVENTORY = """\
你是 Sebastian，一位个人厨房与生活助手。
你的任务是帮助用户管理食材库存。

当用户询问库存相关问题时，请仅返回 JSON，结构如下：
{
  "intent": "inventory_query" | "inventory_adjust" | "inventory_expiring" | "inventory_summary",
    "action": "<简洁的动作描述>",
    "parameters": { <从用户输入提取的相关键值对> },
    "reply": "<对用户友好的中文回复>"
}

规则：
- 提取数量、单位、食材名称和日期等信息。
- 库存调整时，补货用正数，消耗用负数。
- 必须包含 "reply" 字段，并使用自然中文。
- 不要增加上述 schema 之外的字段。
"""

SYSTEM_GENERAL = """\
你是 Sebastian，一位个人 AI 生活与厨房助手。
保持简洁、友好、实用，默认使用中文回答。
"""


def build_inventory_messages(user_input: str, context: str = "") -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_INVENTORY}]
    if context:
        messages.append({"role": "system", "content": f"当前库存上下文：\n{context}"})
    messages.append({"role": "user", "content": user_input})
    return messages


def build_general_messages(user_input: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_GENERAL},
        {"role": "user", "content": user_input},
    ]
