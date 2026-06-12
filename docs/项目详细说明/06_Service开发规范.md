# Service 开发规范

> 业务代码应该放哪里，以及各层边界。

## 核心原则

```
Agent（薄门面）
    ↓
Orchestration（流程控制）
    ↓
Service（业务逻辑）    ← 大部分代码写在这里
    ↓
Repository（数据访问）
    ↓
Database
```

**Service 是业务逻辑的唯一归属地。**

## 正确 vs 错误

### 正确

```python
# services/recipe_agent_service.py
class RecipeAgentService:
    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        if settings.deepseek_api_key:
            result = self._recommend_with_llm(payload)
            if result:
                return result
        return self._recommend_with_template(payload)
```

### 错误

```python
# agents/recipe_agent.py — 不要在这里写业务
class RecipeAgent:
    def recommend(self, payload):
        sql = "SELECT * FROM inventories WHERE ..."
        # ❌ Agent 不应写 SQL
```

```python
# api/routes/agent_tools.py — 不要在这里写业务
def recipe_recommend(payload):
    bmi = payload.weight / (payload.height ** 2)  # ❌ 路由不应算 BMI
```

## Service 分类

### Agent Service（`*_agent_service.py`）

面向 Agent 的业务逻辑，通常被 Orchestration 图调用。

| Service | 职责 | 是否用 LLM |
|---------|------|-----------|
| RecipeAgentService | 菜谱生成 | 是（可降级） |
| HealthAgentService | BMI 与健康建议 | 否（规则计算） |
| EquipmentAgentService | 厨具集合对比 | 否（规则计算） |
| SearchAgentService | 记忆检索 + 摘要 | 否（调用 SearchService） |

### Domain Service

面向领域的通用业务逻辑，可被 Agent Service 或 API 直接调用。

| Service | 职责 |
|---------|------|
| InventoryService | 库存 CRUD、汇总、临期查询 |
| SearchService | Elasticsearch 混合检索 |
| TaskExecutionLogService | Celery 执行日志 |

### Infrastructure Service

横切关注点，不含领域逻辑。

| Service | 职责 |
|---------|------|
| agent_rate_limiter | Redis 滑动窗口限流 |
| agent_task_cache | Redis 任务状态缓存 |
| agent_task_queue | 任务入队 |
| mcp_adapter | MCP 协议适配 |
| embedding_service | 向量嵌入 |

## 编写规范

### 1. 构造函数注入依赖

```python
class RecipeAgentService:
    def __init__(self, inventory_service: InventoryService | None = None) -> None:
        self._inventory_service = inventory_service or InventoryService()
```

便于测试时注入 Mock。

### 2. 方法签名使用 Schema

```python
def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
```

不使用裸 dict，保持类型安全。

### 3. 异常处理

- 业务异常：抛 `app.core.errors` 中的异常（`NotFoundError`, `ValidationError`, `LLMError`）
- API 层负责转为 HTTP 状态码
- Service 层不 import FastAPI

### 4. LLM 调用与降级

```python
try:
    raw = get_llm_client().chat_json(messages)
    return RecipeRecommendResponse.model_validate(raw)
except (LLMError, ValueError) as exc:
    logger.warning("LLM failed, fallback: %s", exc)
    return None  # 调用方决定是否降级
```

Service 负责降级策略，Graph 层不负责。

### 5. 不感知 HTTP

Service 方法不应接收 `Request` 对象，不应返回 HTTP 状态码。

trace_id 通过 `app.core.request_context` 获取（如需日志关联）。

## 何时新建 Service vs 扩展现有 Service

| 场景 | 做法 |
|------|------|
| 新 Agent 能力 | 新建 `*_agent_service.py` |
| 现有 Agent 加字段 | 扩展对应 Agent Service |
| 新 CRUD 资源 | 新建 Domain Service + Repository |
| 横切功能（限流、缓存） | 新建 Infrastructure Service |

## 测试 Service

Service 是最好测试的层——不依赖 HTTP 或 Graph：

```python
def test_equipment_check_missing():
    service = EquipmentAgentService()
    result = service.check(EquipmentCheckRequest(
        equipment_owned=["锅"],
        required_equipment=["锅", "烤箱"],
    ))
    assert result.feasible is False
    assert "烤箱" in result.missing_equipment
```

参考 `tests/test_agent_graphs.py` 中的 Service 注入测试模式。

## 检查清单

编写或审查 Service 代码时确认：

- [ ] 无 SQL / 无直接 ORM 操作（通过 Repository）
- [ ] 无 FastAPI / HTTP 依赖
- [ ] 方法签名使用 Pydantic Schema
- [ ] LLM 调用有超时和降级
- [ ] 依赖通过构造函数注入
- [ ] 有对应单元测试
