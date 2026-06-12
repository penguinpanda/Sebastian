from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.repositories.inventory import PostgresInventoryRepository
from app.schemas.mcp import MCPErrorResponse, MCPInvokeRequest, MCPInvokeResponse, MCPToolSpec, MCPToolsResponse
from app.schemas.agent_tools import EquipmentCheckRequest, HealthAnalyzeRequest, RecipeRecommendRequest, SearchAnswerRequest
from app.services.equipment_agent_service import EquipmentAgentService
from app.services.inventory_service import InventoryService
from app.services.mcp_adapter import MCPInvocationError, MCPToolAdapter
from app.services.health_agent_service import HealthAgentService
from app.services.recipe_agent_service import RecipeAgentService
from app.services.search_agent_service import SearchAgentService
from app.orchestration.agent_graphs import run_equipment_agent, run_health_agent, run_recipe_agent, run_search_agent

router = APIRouter(prefix="/mcp")


def _build_tool_specs() -> list[MCPToolSpec]:
    return [
        MCPToolSpec(
            name="inventory.summary",
            description="Get inventory summary including expiring soon count",
            input_schema={"type": "object", "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 365}}},
            output_schema={"type": "object", "properties": {"total_items": {"type": "integer"}, "expiring_soon": {"type": "integer"}}},
            timeout_ms=5000,
            idempotency_key_required=False,
        ),
        MCPToolSpec(
            name="inventory.expiring",
            description="List inventory items expiring within N days",
            input_schema={"type": "object", "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 365}}},
            output_schema={"type": "object", "properties": {"items": {"type": "array"}}},
            timeout_ms=5000,
            idempotency_key_required=False,
        ),
        MCPToolSpec(
            name="recipe.recommend",
            description="Recommend a recipe based on user goal and available equipment",
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
            timeout_ms=5000,
            idempotency_key_required=False,
        ),
        MCPToolSpec(
            name="health.analyze",
            description="Analyze BMI and suggest daily calories",
            input_schema={
                "type": "object",
                "required": ["user_id", "height_cm", "weight_kg"],
                "properties": {
                    "user_id": {"type": "string"},
                    "height_cm": {"type": "number"},
                    "weight_kg": {"type": "number"},
                    "target_weight_kg": {"type": "number"},
                    "daily_calories_taken": {"type": "integer"},
                },
            },
            output_schema={"type": "object", "properties": {"bmi": {"type": "number"}, "advice": {"type": "string"}}},
            timeout_ms=5000,
            idempotency_key_required=False,
        ),
        MCPToolSpec(
            name="equipment.check",
            description="Check if available equipment is sufficient for the required list",
            input_schema={
                "type": "object",
                "properties": {
                    "equipment_owned": {"type": "array", "items": {"type": "string"}},
                    "required_equipment": {"type": "array", "items": {"type": "string"}},
                },
            },
            output_schema={"type": "object", "properties": {"feasible": {"type": "boolean"}}},
            timeout_ms=5000,
            idempotency_key_required=False,
        ),
        MCPToolSpec(
            name="search.answer",
            description="Answer query based on user memory retrieval",
            input_schema={
                "type": "object",
                "required": ["user_id", "query"],
                "properties": {
                    "user_id": {"type": "string"},
                    "query": {"type": "string"},
                },
            },
            output_schema={"type": "object", "properties": {"summary": {"type": "string"}, "evidence": {"type": "array"}}},
            timeout_ms=5000,
            idempotency_key_required=False,
        ),
    ]


def get_mcp_adapter(db: Session = Depends(get_db_session)) -> MCPToolAdapter:
    inventory_service = InventoryService(repository=PostgresInventoryRepository(db))
    recipe_service = RecipeAgentService(inventory_service=inventory_service)
    health_service = HealthAgentService()
    equipment_service = EquipmentAgentService()
    search_service = SearchAgentService()
    # Removed the previous service initializations
    # recipe_service = RecipeAgentService(inventory_service=inventory_service)
    # health_service = HealthAgentService()
    # equipment_service = EquipmentAgentService()
    # search_service = SearchAgentService()

    def inventory_summary_handler(payload: dict[str, Any]) -> dict[str, Any]:
        days = int(payload.get("days", 7))
        if days < 1 or days > 365:
            raise ValueError("days must be between 1 and 365")
        summary = inventory_service.summary(days=days)
        return {"days": days, "total_items": summary.total_items, "expiring_soon": summary.expiring_soon}

    def inventory_expiring_handler(payload: dict[str, Any]) -> dict[str, Any]:
        days = int(payload.get("days", 7))
        if days < 1 or days > 365:
            raise ValueError("days must be between 1 and 365")
        items = inventory_service.expiring_items(days)
        return {
            "days": days,
            "items": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "expire_date": item.expire_date.isoformat(),
                    "days_left": item.days_left,
                }
                for item in items
            ],
        }

    def recipe_recommend_handler(payload: dict[str, Any]) -> dict[str, Any]:
        response = run_recipe_agent(RecipeRecommendRequest.model_validate(payload), recipe_service=recipe_service)
        return response.model_dump(mode="json")

    def health_analyze_handler(payload: dict[str, Any]) -> dict[str, Any]:
        response = run_health_agent(HealthAnalyzeRequest.model_validate(payload), service=health_service)
        return response.model_dump(mode="json")

    def equipment_check_handler(payload: dict[str, Any]) -> dict[str, Any]:
        response = run_equipment_agent(EquipmentCheckRequest.model_validate(payload), service=equipment_service)
        return response.model_dump(mode="json")

    def search_answer_handler(payload: dict[str, Any]) -> dict[str, Any]:
        response = run_search_agent(SearchAnswerRequest.model_validate(payload), service=search_service)
        return response.model_dump(mode="json")

    handlers = {
        "inventory.summary": inventory_summary_handler,
        "inventory.expiring": inventory_expiring_handler,
        "recipe.recommend": recipe_recommend_handler,
        "health.analyze": health_analyze_handler,
        "equipment.check": equipment_check_handler,
        "search.answer": search_answer_handler,
    }
    return MCPToolAdapter(tool_specs=_build_tool_specs(), handlers=handlers)


@router.get("/tools", response_model=MCPToolsResponse)
def list_tools(adapter: MCPToolAdapter = Depends(get_mcp_adapter)) -> MCPToolsResponse:
    return MCPToolsResponse(tools=adapter.list_tools())


@router.post("/invoke", response_model=MCPInvokeResponse)
def invoke_tool(payload: MCPInvokeRequest, request: Request, adapter: MCPToolAdapter = Depends(get_mcp_adapter)) -> MCPInvokeResponse:
    request.state.user_id = payload.user_id
    request.state.action = payload.action

    if not payload.trace_id:
        trace_id = getattr(request.state, "trace_id", None)
        if trace_id:
            payload = payload.model_copy(update={"trace_id": trace_id})

    try:
        return adapter.invoke(payload)
    except MCPInvocationError as exc:
        detail = MCPErrorResponse(code=exc.code, message=exc.message, timestamp=datetime.now(timezone.utc)).model_dump(mode="json")
        if exc.code == "VALIDATION_ERROR":
            raise HTTPException(status_code=400, detail=detail) from exc
        if exc.code == "RETRYABLE_ERROR":
            raise HTTPException(status_code=503, detail=detail) from exc
        if exc.code == "BUSINESS_ERROR":
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=500, detail=detail) from exc
