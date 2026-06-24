"""快速验证脚本：检查 A2A 重构后的模块导入是否正常。"""
from app.a2a.schemas import AgentCard, Task, Message, TaskState, Artifact
print("OK A2A schemas")

from app.a2a.agent_card import build_global_agent_card, build_agent_card
card = build_global_agent_card()
print(f"OK Agent Card: {card.name}")

from app.context.token_counter import TokenCounter
tc = TokenCounter()
print(f"OK TokenCounter: {tc.encoding_name}")

from app.context.budget import ContextBudget
budget = ContextBudget()
budget.allocate("system", 100, "test")
print(f"OK ContextBudget: {budget.used}/{budget.max_context_tokens}")

from app.context.history_manager import ConversationHistoryManager
print("OK HistoryManager")

from app.context.compressor import ContextCompressor
print("OK Compressor")

from app.a2a.task_manager import TaskManager
print("OK TaskManager")

from app.agents.base import BaseAgent
print("OK BaseAgent")

# 检查每个 Agent 是否继承 BaseAgent 并定义了 agent_card
from app.agents import (
    RecipeAgent, HealthAgent, SearchAgent, EquipmentAgent, InventoryAgent, RouterAgent,
)
for name, cls in [
    ("RecipeAgent", RecipeAgent),
    ("HealthAgent", HealthAgent),
    ("SearchAgent", SearchAgent),
    ("EquipmentAgent", EquipmentAgent),
    ("InventoryAgent", InventoryAgent),
    ("RouterAgent", RouterAgent),
]:
    card = cls.agent_card
    print(f"OK {name}: card={card.name} skills={len(card.skills)}")

print("ALL CHECKS PASSED")
