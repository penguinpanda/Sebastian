# API 开发指南

> 如何新增或修改 HTTP 接口。

## 路由组织

所有业务路由统一挂载在 `/api` 前缀下（`app/api/router.py`）：

| 前缀 | 路由文件 | 用途 |
|------|----------|------|
| `/api/health` | `health.py` | 健康 / 就绪检查 |
| `/api/inventory` | `inventory.py` | 库存 CRUD |
| `/api/agent` | `agent.py` | 聊天 + 任务状态 |
| `/api/agents` | `agent_tools.py` | 专用 Agent 工具 |
| `/api/search` | `search.py` | 记忆检索 |
| `/api/mcp` | `mcp.py` | MCP 协议 |
| `/api/tasks` | `task_history.py` | Celery 任务历史 |

## 接口规范

### 通用约定

- 请求/响应体使用 JSON
- 使用 Pydantic Schema 校验（`app/schemas/`）
- 成功响应直接返回 Schema 对象
- 业务错误通过 `HTTPException` 返回，带稳定 `detail` 结构
- 每个路由设置 `request.state.action` 供日志使用
- 支持 `x-trace-id` 请求头透传

### 示例：Recipe 推荐

**请求：**

```
POST /api/agents/recipe/recommend
Content-Type: application/json
x-trace-id: optional-trace-id
```

```json
{
  "user_id": "demo",
  "meal_type": "dinner",
  "target_calories": 600,
  "available_equipment": ["锅", "平底锅"],
  "dietary_preferences": ["少油", "高蛋白"]
}
```

**响应：**

```json
{
  "title": "晚餐能量碗",
  "rationale": "根据你当前库存数量（3）和饮食偏好...",
  "estimated_calories": 580,
  "steps": ["优先使用现有库存...", "采用少油烹饪..."],
  "required_equipment": ["锅", "砧板"],
  "feasible": true,
  "missing_equipment": [],
  "missing_ingredients": []
}
```

**Schema 定义：** `app/schemas/agent_tools.py`

### 示例：Health 分析

**请求：**

```
POST /api/agents/health/analyze
```

```json
{
  "user_id": "demo",
  "height_cm": 175,
  "weight_kg": 70,
  "target_weight_kg": 65,
  "daily_calories_taken": 1800
}
```

**响应：**

```json
{
  "bmi": 22.86,
  "bmi_category": "normal",
  "suggested_daily_calories": 1850,
  "advice": "建议保持均衡饮食，并维持稳定日常活动量。"
}
```

### 示例：Equipment 检查

**请求：**

```
POST /api/agents/equipment/check
```

```json
{
  "equipment_owned": ["锅", "平底锅"],
  "required_equipment": ["锅", "烤箱", "砧板"]
}
```

**响应：**

```json
{
  "feasible": false,
  "missing_equipment": ["oven", "砧板"],
  "suggestion": "仍可通过替代烹饪方式，或选择免烹饪菜谱完成制作。"
}
```

### 示例：Inventory CRUD

**创建：**

```
POST /api/inventory
```

```json
{
  "name": "鸡蛋",
  "quantity": 12,
  "unit": "个",
  "expire_date": "2026-06-20",
  "note": "冰箱上层"
}
```

**调整：**

```
PATCH /api/inventory/{item_id}/adjust
```

```json
{
  "amount": -2,
  "note": "做了炒蛋"
}
```

### 示例：Agent Chat

**请求：**

```
POST /api/agent/chat
```

```json
{
  "message": "我有哪些临期食材？",
  "user_id": "demo"
}
```

**响应：**

```json
{
  "reply": "您当前有 2 项食材将在 7 天内过期...",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**查询任务状态：**

```
GET /api/agent/tasks/{task_id}
```

## 新增 API 步骤

1. **定义 Schema** — `app/schemas/`
2. **实现 Service** — `app/services/`
3. **创建路由** — `app/api/routes/`
4. **注册路由** — `app/api/router.py` 中添加 `include_router`
5. **编写测试** — `tests/test_*_api.py`

### 路由模板

```python
from fastapi import APIRouter, Depends, Request

router = APIRouter(prefix="/my-resource")

@router.post("/action", response_model=MyResponse)
def my_action(
    payload: MyRequest,
    request: Request,
    service: MyService = Depends(get_my_service),
) -> MyResponse:
    request.state.user_id = payload.user_id
    request.state.action = "my_action"
    try:
        return service.do_action(payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

## 依赖注入

`app/api/dependencies.py` 提供通用依赖：

```python
def get_db_session() -> Generator[Session, None, None]:
    ...

def get_inventory_service(db: Session = Depends(get_db_session)) -> InventoryService:
    return InventoryService(repository=PostgresInventoryRepository(db))
```

Agent 路由在 `agent_tools.py` 中自行组装依赖链。

## 错误码约定

| HTTP 状态 | 场景 |
|-----------|------|
| 400 | 参数校验失败 |
| 404 | 资源不存在 |
| 409 | 业务冲突（MCP BUSINESS_ERROR） |
| 429 | Agent 限流 |
| 503 | 依赖不可用 / MCP 可重试错误 |
| 500 | 未预期错误 |

## 完整 API 列表

详见 [使用指南.md](./使用指南.md) 第 4 节，或在本地访问：

```
http://127.0.0.1:8000/docs
```

FastAPI 自动生成的 Swagger UI 包含所有端点的交互式文档。
