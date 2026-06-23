from __future__ import annotations

from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.schemas.agent_tools import (
    EquipmentCheckRequest,
    EquipmentCheckResponse,
    HealthAnalyzeRequest,
    HealthAnalyzeResponse,
    InventoryOnlyRecipeRequest,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
    SearchAnswerRequest,
    SearchAnswerResponse,
)
from app.services.equipment_agent_service import EquipmentAgentService
from app.services.health_agent_service import HealthAgentService
from app.services.recipe_agent_service import RecipeAgentService
from app.services.search_agent_service import SearchAgentService


class GraphState(TypedDict, total=False):
    request: Any
    result: Any
    search_result: SearchAnswerResponse
    equipment_result: EquipmentCheckResponse

def _as_model(payload: Any, model_type: type[Any]) -> Any:
    if isinstance(payload, model_type):
        return payload
    return model_type.model_validate(payload)


def _search_query_for_recipe(request: RecipeRecommendRequest) -> str:
    keywords = [request.meal_type, *request.dietary_preferences, *request.available_equipment]
    query = " ".join(item.strip() for item in keywords if item.strip())
    return query or request.meal_type


def _build_single_step_graph(handler: Any):
    graph = StateGraph(GraphState)
    graph.add_node("execute", handler)
    graph.add_edge(START, "execute")
    graph.add_edge("execute", END)
    return graph.compile()


def _build_health_graph(service: HealthAgentService | None = None):
    service = service or HealthAgentService()

    def execute(state: GraphState) -> GraphState:
        request = _as_model(state["request"], HealthAnalyzeRequest)
        return {"result": service.analyze(request)}

    return _build_single_step_graph(execute)


def _build_equipment_graph(service: EquipmentAgentService | None = None):
    service = service or EquipmentAgentService()

    def execute(state: GraphState) -> GraphState:
        request = _as_model(state["request"], EquipmentCheckRequest)
        return {"result": service.check(request)}

    return _build_single_step_graph(execute)


def _build_search_graph(service: SearchAgentService | None = None):
    service = service or SearchAgentService()

    def execute(state: GraphState) -> GraphState:
        request = _as_model(state["request"], SearchAnswerRequest)
        return {"result": service.answer(request)}

    return _build_single_step_graph(execute)


def _build_recipe_graph(
    recipe_service: RecipeAgentService | None = None,
    search_service: SearchAgentService | None = None,
    equipment_service: EquipmentAgentService | None = None,
):
    recipe_service = recipe_service or RecipeAgentService()
    equipment_service = (equipment_service or EquipmentAgentService())
    search_graph = _build_search_graph(search_service)

    def collect_context(state: GraphState) -> GraphState:
        request = _as_model(state["request"], RecipeRecommendRequest)
        search_result = search_graph.invoke({"request": SearchAnswerRequest(user_id=request.user_id, query=_search_query_for_recipe(request))})
        return {
            **state,
            "request": request,
            "search_result": search_result["result"],
        }

    def compose(state: GraphState) -> GraphState:
        request = _as_model(state["request"], RecipeRecommendRequest)
        base = recipe_service.recommend(request)
        search_result = state.get("search_result")

        rationale = base.rationale
        steps = list(base.steps)
        missing = list(base.missing_ingredients)

        if search_result and search_result.evidence:
            rationale = f"{rationale} 记忆提示：{', '.join(search_result.evidence[:2])}。"

        return {
            "result": base.model_copy(
                update={
                    "rationale": rationale,
                    "steps": steps,
                    "required_equipment": list(base.required_equipment),
                    "missing_ingredients": missing,
                }
            )
        }
    
    def check_equipment(state: GraphState) -> GraphState:
        request = _as_model(
            state["request"],
            RecipeRecommendRequest,
        )

        recipe = _as_model(
            state["result"],
            RecipeRecommendResponse,
        )

        equipment_result = equipment_service.check(
            EquipmentCheckRequest(
                equipment_owned=request.available_equipment,
                required_equipment=recipe.required_equipment,
            )
        )

        return {
            **state,
            "equipment_result": equipment_result,
        }
    
    def finalize(state: GraphState) -> GraphState:
        recipe = _as_model(
            state["result"],
            RecipeRecommendResponse,
        )

        equipment_result = state.get(
            "equipment_result"
        )

        if equipment_result:
            rationale = recipe.rationale

            if not equipment_result.feasible:
                rationale += (
                    "\n缺少厨具："
                    + "、".join(
                        equipment_result.missing_equipment
                    )
                    + "。"
                    + equipment_result.suggestion
                )

            recipe = recipe.model_copy(
                update={
                    "rationale": rationale,

                    # 同步写回校验结果
                    "feasible":
                        equipment_result.feasible,

                    "missing_equipment":
                        equipment_result.missing_equipment,
                }
            )

        return {
            "result": recipe
        }

    graph = StateGraph(GraphState)
    graph.add_node("collect_context", collect_context)
    graph.add_node("compose", compose)
    graph.add_node("check_equipment", check_equipment)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "collect_context")
    graph.add_edge("collect_context", "compose")
    graph.add_edge("compose", "check_equipment")
    graph.add_edge("check_equipment", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


@lru_cache(maxsize=1)
def _default_health_graph():
    return _build_health_graph()


@lru_cache(maxsize=1)
def _default_equipment_graph():
    return _build_equipment_graph()


@lru_cache(maxsize=1)
def _default_search_graph():
    return _build_search_graph()


@lru_cache(maxsize=1)
def _default_recipe_graph():
    return _build_recipe_graph()


def run_health_agent(payload: HealthAnalyzeRequest, service: HealthAgentService | None = None) -> HealthAnalyzeResponse:
    graph = _build_health_graph(service) if service is not None else _default_health_graph()
    result = graph.invoke({"request": payload})
    return result["result"]


def run_equipment_agent(payload: EquipmentCheckRequest, service: EquipmentAgentService | None = None) -> EquipmentCheckResponse:
    graph = _build_equipment_graph(service) if service is not None else _default_equipment_graph()
    result = graph.invoke({"request": payload})
    return result["result"]


def run_search_agent(payload: SearchAnswerRequest, service: SearchAgentService | None = None) -> SearchAnswerResponse:
    graph = _build_search_graph(service) if service is not None else _default_search_graph()
    result = graph.invoke({"request": payload})
    return result["result"]


def run_recipe_agent(
    payload: RecipeRecommendRequest,
    recipe_service: RecipeAgentService | None = None,
    search_service: SearchAgentService | None = None,
    equipment_service: EquipmentAgentService | None = None,
) -> RecipeRecommendResponse:
    if recipe_service is None and search_service is None and equipment_service is None:
        graph = _default_recipe_graph()
    else:
        graph = _build_recipe_graph(recipe_service=recipe_service, search_service=search_service, equipment_service=equipment_service)
    result = graph.invoke({"request": payload})
    return result["result"]


# ---------- 仅使用库存材料生成菜谱（跳过搜索记忆和厨具检查） ----------

def _build_recipe_graph_inventory_only(
    recipe_service: RecipeAgentService | None = None,
):
    """仅使用库存材料生成菜谱的简化图：直接调用 Service，跳过搜索/厨具子图。"""
    recipe_service = recipe_service or RecipeAgentService()

    def execute(state: GraphState) -> GraphState:
        request = _as_model(state["request"], InventoryOnlyRecipeRequest)
        result = recipe_service.recommend_from_inventory_only(request)
        return {"result": result}

    return _build_single_step_graph(execute)


@lru_cache(maxsize=1)
def _default_recipe_graph_inventory_only():
    return _build_recipe_graph_inventory_only()


def run_recipe_agent_inventory_only(
    payload: InventoryOnlyRecipeRequest,
    recipe_service: RecipeAgentService | None = None,
) -> RecipeRecommendResponse:
    if recipe_service is None:
        graph = _default_recipe_graph_inventory_only()
    else:
        graph = _build_recipe_graph_inventory_only(recipe_service=recipe_service)
    result = graph.invoke({"request": payload})
    return result["result"]
