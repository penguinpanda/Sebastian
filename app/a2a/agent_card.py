"""Agent Card 定义 — 每个 Agent 的自描述元数据。

每个 Agent Card 通过 GET /.well-known/agent.json 或 /a2a/agents/{name}/card 暴露。
"""

from __future__ import annotations

from app.a2a.schemas import AgentCapabilities, AgentCard, AgentSkill


def build_global_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """全局 Agent Card — Sebastian 系统的统一入口。"""
    return AgentCard(
        name="Sebastian",
        description="个人生活与厨房 AI 助手系统，集成菜谱推荐、健康分析、库存管理、知识搜索和厨具检查",
        url=f"{base_url}/a2a",
        version="0.2.0",
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            state_transition_history=True,
        ),
        skills=[
            AgentSkill(
                id="router.chat",
                name="智能路由",
                description="识别用户意图并分发到合适的子 Agent",
                examples=["我想吃低卡的午餐", "帮我算一下BMI"],
            ),
        ],
        default_input_modes=["text"],
        default_output_modes=["text", "application/json"],
    )


def build_router_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Router Agent Card。"""
    return AgentCard(
        name="Router Agent",
        description="意图识别与任务分发 — 分析用户消息，路由到最合适的子 Agent",
        url=f"{base_url}/a2a",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="router.chat",
                name="智能路由",
                description="分析用户意图（recipe/health/inventory/search/equipment/general）并分发",
                examples=["推荐一道低脂菜", "我的BMI正常吗", "冰箱里还有什么食材"],
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            ),
        ],
    )


def build_recipe_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Recipe Agent Card。"""
    return AgentCard(
        name="Recipe Agent",
        description="菜谱推荐助手 — 根据用户需求、库存食材和饮食偏好推荐菜谱",
        url=f"{base_url}/a2a",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="recipe.recommend",
                name="菜谱推荐",
                description="根据餐食类型、目标热量、可用厨具和饮食偏好推荐菜谱",
                examples=["推荐一份低卡午餐", "有什么用鸡胸肉做的菜"],
                input_schema={
                    "type": "object",
                    "required": ["user_id"],
                    "properties": {
                        "user_id": {"type": "string"},
                        "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]},
                        "target_calories": {"type": "integer", "minimum": 200, "maximum": 2000},
                        "available_equipment": {"type": "array", "items": {"type": "string"}},
                        "dietary_preferences": {"type": "array", "items": {"type": "string"}},
                    },
                },
                output_schema={"type": "object", "properties": {"title": {"type": "string"}, "steps": {"type": "array"}}},
            ),
            AgentSkill(
                id="recipe.recommend-from-inventory",
                name="库存菜谱推荐",
                description="仅使用当前库存食材生成菜谱",
                examples=["用冰箱里的东西能做什么"],
            ),
        ],
    )


def build_health_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Health Agent Card。"""
    return AgentCard(
        name="Health Agent",
        description="健康分析助手 — BMI 计算、饮食热量分析、个性化健康建议",
        url=f"{base_url}/a2a",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="health.analyze",
                name="健康分析",
                description="分析 BMI、建议每日热量摄入，结合饮食历史给出个性化建议",
                examples=["我身高175体重80，需要减肥吗", "分析一下我最近的饮食"],
                input_schema={
                    "type": "object",
                    "required": ["user_id", "height_cm", "weight_kg"],
                    "properties": {
                        "user_id": {"type": "string"},
                        "height_cm": {"type": "number"},
                        "weight_kg": {"type": "number"},
                        "target_weight_kg": {"type": "number"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "bmi": {"type": "number"},
                        "bmi_category": {"type": "string"},
                        "suggested_daily_calories": {"type": "number"},
                        "advice": {"type": "string"},
                    },
                },
            ),
        ],
    )


def build_search_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Search Agent Card。"""
    return AgentCard(
        name="Search Agent",
        description="知识搜索助手 — 检索记忆库并用 LLM 生成自然语言摘要",
        url=f"{base_url}/a2a",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="search.answer",
                name="知识搜索",
                description="混合检索（词法+向量+RRF）ES 记忆库，LLM 生成摘要",
                examples=["花生过敏怎么办", "减脂期间应该吃什么"],
                input_schema={
                    "type": "object",
                    "required": ["user_id", "query"],
                    "properties": {
                        "user_id": {"type": "string"},
                        "query": {"type": "string"},
                    },
                },
            ),
        ],
    )


def build_equipment_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Equipment Agent Card。"""
    return AgentCard(
        name="Equipment Agent",
        description="厨具顾问 — 检查所需厨具是否完备，给出替代方案建议",
        url=f"{base_url}/a2a",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="equipment.check",
                name="厨具检查",
                description="对比拥有的和菜谱所需的厨具，给出缺失清单和替代建议",
                examples=["做蛋糕需要什么厨具", "没有烤箱能用什么替代"],
                input_schema={
                    "type": "object",
                    "required": ["equipment_owned", "required_equipment"],
                    "properties": {
                        "equipment_owned": {"type": "array", "items": {"type": "string"}},
                        "required_equipment": {"type": "array", "items": {"type": "string"}},
                    },
                },
            ),
        ],
    )


def build_inventory_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Inventory Agent Card。"""
    return AgentCard(
        name="Inventory Agent",
        description="库存管理助手 — 食材增删改查、过期提醒、库存统计",
        url=f"{base_url}/a2a",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="inventory.query",
                name="库存查询",
                description="查看当前库存物品",
                examples=["冰箱里有什么", "查看所有食材"],
            ),
            AgentSkill(
                id="inventory.adjust",
                name="库存调整",
                description="增加或减少库存物品数量",
                examples=["买了3个鸡蛋", "用掉了200克鸡胸肉"],
            ),
            AgentSkill(
                id="inventory.expiring",
                name="过期提醒",
                description="查看即将过期的食材",
                examples=["有什么快过期的东西", "最近3天过期的食材"],
            ),
            AgentSkill(
                id="inventory.summary",
                name="库存概览",
                description="查看库存统计摘要",
                examples=["库存还有多少东西"],
            ),
        ],
    )


# ── 所有 Agent Card 的注册表 ────────────────────────────────────────

AGENT_CARD_BUILDERS: dict[str, callable] = {
    "global": build_global_agent_card,
    "router": build_router_agent_card,
    "recipe": build_recipe_agent_card,
    "health": build_health_agent_card,
    "search": build_search_agent_card,
    "equipment": build_equipment_agent_card,
    "inventory": build_inventory_agent_card,
}


def build_agent_card(agent_name: str, base_url: str = "http://localhost:8000") -> AgentCard:
    """根据 Agent 名称获取对应的 Agent Card。"""
    builder = AGENT_CARD_BUILDERS.get(agent_name)
    if builder is None:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(AGENT_CARD_BUILDERS)}")
    return builder(base_url=base_url)
