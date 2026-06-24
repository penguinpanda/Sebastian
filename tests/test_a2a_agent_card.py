"""A2A Agent Card 测试 — 验证 Agent Card 定义和端点。"""

from __future__ import annotations

import httpx
import pytest

from app.a2a.agent_card import (
    AGENT_CARD_BUILDERS,
    build_agent_card,
    build_equipment_agent_card,
    build_global_agent_card,
    build_health_agent_card,
    build_inventory_agent_card,
    build_recipe_agent_card,
    build_router_agent_card,
    build_search_agent_card,
)
from app.a2a.schemas import AgentCard
from app.main import app


# ── 静态定义测试 ──────────────────────────────────────────────

class TestAgentCardDefinitions:
    """测试各 Agent Card 的静态定义是否符合 A2A 规范。"""

    @pytest.mark.parametrize("name,builder", [
        ("global", build_global_agent_card),
        ("router", build_router_agent_card),
        ("recipe", build_recipe_agent_card),
        ("health", build_health_agent_card),
        ("search", build_search_agent_card),
        ("equipment", build_equipment_agent_card),
        ("inventory", build_inventory_agent_card),
    ])
    def test_agent_card_has_required_fields(self, name: str, builder) -> None:
        """所有 Agent Card 必须包含 name, description, url, skills。"""
        card = builder()
        assert isinstance(card, AgentCard)
        assert card.name, f"{name}: name is empty"
        assert card.description, f"{name}: description is empty"
        assert card.url, f"{name}: url is empty"
        assert isinstance(card.skills, list), f"{name}: skills is not a list"
        assert card.version, f"{name}: version is empty"

    @pytest.mark.parametrize("name,builder,expected_skill_count", [
        ("global", build_global_agent_card, 1),
        ("router", build_router_agent_card, 1),
        ("recipe", build_recipe_agent_card, 2),
        ("health", build_health_agent_card, 1),
        ("search", build_search_agent_card, 1),
        ("equipment", build_equipment_agent_card, 1),
        ("inventory", build_inventory_agent_card, 4),
    ])
    def test_agent_card_skill_count(self, name, builder, expected_skill_count):
        """验证各 Agent Card 的技能数量。"""
        card = builder()
        assert len(card.skills) == expected_skill_count, (
            f"{name}: expected {expected_skill_count} skills, got {len(card.skills)}"
        )

    def test_each_skill_has_id_and_name(self) -> None:
        """每个技能必须包含 id 和 name。"""
        for name, builder in AGENT_CARD_BUILDERS.items():
            card = builder()
            for skill in card.skills:
                assert skill.id, f"{name}.skills[{skill.id}]: empty id"
                assert skill.name, f"{name}.skills[{skill.id}]: empty name"

    def test_skill_ids_are_unique_within_agent(self) -> None:
        """每个 Agent Card 内部技能 ID 必须唯一（跨 Agent 允许同名）。"""
        for name, builder in AGENT_CARD_BUILDERS.items():
            card = builder()
            ids_within_card: set[str] = set()
            for skill in card.skills:
                assert skill.id not in ids_within_card, (
                    f"{name}: duplicate skill id '{skill.id}' within same card"
                )
                ids_within_card.add(skill.id)

    def test_global_card_has_streaming_capability(self) -> None:
        """全局 Agent Card 必须声明流式能力。"""
        card = build_global_agent_card()
        assert card.capabilities.streaming is True

    def test_build_agent_card_by_name(self) -> None:
        """build_agent_card() 按名称获取 Agent Card。"""
        card = build_agent_card("recipe")
        assert card.name == "Recipe Agent"

    def test_build_agent_card_unknown_raises(self) -> None:
        """不存在的 Agent 名称抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unknown agent"):
            build_agent_card("nonexistent")

    def test_agent_card_default_input_modes(self) -> None:
        """所有 Agent Card 应默认支持 text 输入。"""
        for name, builder in AGENT_CARD_BUILDERS.items():
            card = builder()
            assert "text" in card.default_input_modes, f"{name}: missing text input mode"


# ── HTTP 端点测试 ──────────────────────────────────────────────

class TestAgentCardEndpoints:
    """测试 Agent Card HTTP 端点。"""

    @pytest.mark.asyncio
    async def test_well_known_agent_json(self) -> None:
        """GET /.well-known/agent.json 返回 200 + 有效 Agent Card。"""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/.well-known/agent.json")

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Sebastian"
        assert "skills" in body
        assert "capabilities" in body

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_name", [
        "recipe", "health", "search", "equipment", "inventory",
    ])
    async def test_agent_card_endpoint(self, agent_name: str) -> None:
        """GET /api/a2a/agents/{name}/card 返回对应 Agent Card。"""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(f"/api/a2a/agents/{agent_name}/card")

        assert response.status_code == 200
        body = response.json()
        assert body["name"], f"{agent_name}: name is empty"
        assert len(body["skills"]) > 0, f"{agent_name}: no skills"

    @pytest.mark.asyncio
    async def test_agent_card_unknown_returns_404(self) -> None:
        """不存在的 Agent 返回 404。"""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/a2a/agents/unknown/card")

        assert response.status_code == 404
