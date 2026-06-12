# Agent 开发指南

> 如何新增或修改一个 Agent。

## Agent 在本项目中的定位

Agent 是**薄门面**：

```python
class EquipmentAgent:
    def check(self, payload):
        return run_equipment_agent(payload, service=self._service)
```

Agent 不做业务计算，只负责：
1. 接收结构化请求（Pydantic Schema）
2. 委托给 Orchestration 层执行
3. 返回结构化响应

## 现有 Agent 一览

| Agent | 入口方法 | Graph | Service |
|-------|----------|-------|---------|
| RecipeAgent | `recommend()` | 多节点 recipe_graph | RecipeAgentService |
| HealthAgent | `analyze()` | 单步 health_graph | HealthAgentService |
| EquipmentAgent | `check()` | 单步 equipment_graph | EquipmentAgentService |
| SearchAgent | `answer()` | 单步 search_graph | SearchAgentService |

## 新增 Agent 完整步骤

以新增 `NutritionAgent`（营养分析）为例：

### 步骤 1：定义 Schema

`app/schemas/agent_tools.py`：

```python
class NutritionAnalyzeRequest(BaseModel):
    user_id: str
    daily_intake: dict[str, float]  # {"protein": 80, "carbs": 200, ...}

class NutritionAnalyzeResponse(BaseModel):
    balance_score: float
    suggestions: list[str]
```

### 步骤 2：创建 Service

`app/services/nutrition_agent_service.py`：

```python
class NutritionAgentService:
    def analyze(self, payload: NutritionAnalyzeRequest) -> NutritionAnalyzeResponse:
        # 业务逻辑放这里
        ...
```

**规则：** 所有业务逻辑、LLM 调用、Repository 访问都在 Service 层。

### 步骤 3：创建 Agent 门面

`app/agents/nutrition_agent.py`：

```python
from app.orchestration.agent_graphs import run_nutrition_agent

class NutritionAgent:
    def __init__(self, service: NutritionAgentService | None = None) -> None:
        self._service = service or NutritionAgentService()

    def analyze(self, payload: NutritionAnalyzeRequest) -> NutritionAnalyzeResponse:
        return run_nutrition_agent(payload, service=self._service)
```

### 步骤 4：添加 Orchestration Graph

`app/orchestration/agent_graphs.py`：

```python
def _build_nutrition_graph(service: NutritionAgentService | None = None):
    service = service or NutritionAgentService()

    def execute(state: GraphState) -> GraphState:
        request = _as_model(state["request"], NutritionAnalyzeRequest)
        return {"result": service.analyze(request)}

    return _build_single_step_graph(execute)


def run_nutrition_agent(payload, service=None):
    graph = _build_nutrition_graph(service) if service else _default_nutrition_graph()
    result = graph.invoke({"request": payload})
    return result["result"]
```

单步 Agent 使用 `_build_single_step_graph()` 模板即可。

多步 Agent（如 Recipe）参考 `_build_recipe_graph()` 自行添加节点和边。

### 步骤 5：注册 Agent

`app/agents/__init__.py`：

```python
from app.agents.nutrition_agent import NutritionAgent

__all__ = [..., "NutritionAgent"]
```

### 步骤 6：添加 API 路由

`app/api/routes/agent_tools.py`：

```python
@router.post("/nutrition/analyze", response_model=NutritionAnalyzeResponse)
def nutrition_analyze(
    payload: NutritionAnalyzeRequest,
    request: Request,
    agent: NutritionAgent = Depends(get_nutrition_agent),
) -> NutritionAnalyzeResponse:
    request.state.user_id = payload.user_id
    request.state.action = "nutrition_analyze"
    return agent.analyze(payload)
```

### 步骤 7：编写测试

`tests/test_nutrition_agent.py`：

```python
def test_nutrition_analyze():
    service = NutritionAgentService()
    result = run_nutrition_agent(NutritionAnalyzeRequest(...), service=service)
    assert result.balance_score >= 0
```

### 步骤 8：（可选）加入 Recipe 子图

如果新 Agent 需要在 Recipe 流程中被调用，在 `_build_recipe_graph()` 中添加节点：

```python
graph.add_node("analyze_nutrition", analyze_nutrition_node)
graph.add_edge("compose", "analyze_nutrition")
graph.add_edge("analyze_nutrition", "check_equipment")
```

## 修改现有 Agent

| 需求 | 改哪里 |
|------|--------|
| 改返回字段 | `schemas/agent_tools.py` |
| 改业务逻辑 | `services/*_agent_service.py` |
| 改流程顺序 | `orchestration/agent_graphs.py` |
| 改 API 路径 | `api/routes/agent_tools.py` |

## Agent 开发检查清单

新增 Agent 时必须包含：

- [ ] Schema（Request + Response）
- [ ] Service（业务逻辑）
- [ ] Agent 门面类
- [ ] Orchestration Graph + `run_*_agent()` 函数
- [ ] API 路由
- [ ] 单元测试
- [ ] 在 `agents/__init__.py` 注册

详见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 常见错误

| 错误做法 | 正确做法 |
|----------|----------|
| 在 Agent 里写 SQL | 通过 Service → Repository |
| 在 Agent 里直接调 LLM | 在 Service 里调 `get_llm_client()` |
| 跳过 Graph 直接调 Service | 保持 Agent → Graph → Service 一致性 |
| 在 Graph 节点里写 HTTP 逻辑 | HTTP 只在 API 层 |
