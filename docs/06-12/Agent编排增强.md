# Agent 编排增强

> 更新时间: 2026-06-12

## 1. 变更概述

本次对两个 Agent 的编排逻辑做了增强：

| Agent | 变更类型 | 说明 |
|-------|---------|------|
| Recipe Agent | 图结构增强 | 新增 `check_equipment` + `finalize` 节点，厨具检查结果写入响应 |
| Recipe Agent | 新图 | 新增 `_build_recipe_graph_inventory_only()`，仅库存模式简化编排 |
| Health Agent | 数据注入 | 自动读取 `UserProfile` + `MealHistory`，无需前端传参 |

## 2. Recipe Agent 图结构变更

### 2.1 旧图结构（变更前）

```
START → collect_context → compose → END
```

2 个节点：收集搜索记忆 → LLM 生成菜谱。

### 2.2 新图结构（变更后）

```
START → collect_context → compose → check_equipment → finalize → END
```

4 个节点流水线：

```mermaid
flowchart LR
    START --> A[collect_context<br/>搜索记忆]
    A --> B[compose<br/>LLM 生成菜谱]
    B --> C[check_equipment<br/>厨具检查]
    C --> D[finalize<br/>结果汇总]
    D --> END
```

### 2.3 各节点职责

| 节点 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `collect_context` | `RecipeRecommendRequest` | `search_result` | 调用 Search 子图，检索用户饮食偏好/禁忌 |
| `compose` | request + search_result | `result` (RecipeRecommendResponse) | LLM 生成菜谱，记忆提示注入 rationale |
| `check_equipment` | request + result | `equipment_result` | 用 `EquipmentAgentService.check()` 比对厨具 |
| `finalize` | result + equipment_result | `result` (final) | 汇总：不可行时在 rationale 追加厨具建议，同步写入 `feasible` 和 `missing_equipment` |

### 2.4 GraphState 变更

```python
class GraphState(TypedDict, total=False):
    request: Any
    result: Any
    search_result: SearchAnswerResponse
    equipment_result: EquipmentCheckResponse  # 🆕 新增
```

### 2.5 RecipeRecommendResponse 增强

```python
class RecipeRecommendResponse(BaseModel):
    # ... 原有字段 ...
    required_equipment: list[str]     # LLM 列出所需厨具
    feasible: bool = True             # 🆕 厨具是否满足
    missing_equipment: list[str]      # 🆕 缺少的厨具
```

`check_equipment` 节点的结果回写到这两个字段，前端可直接展示厨具可行性。

## 3. 仅库存菜谱图（新增）

### `_build_recipe_graph_inventory_only()`

```
START → execute → END
```

单节点图，跳过搜索记忆和厨具检查，直接调用 `RecipeAgentService.recommend_from_inventory_only()`。

详见 [仅库存菜谱生成](./仅库存菜谱生成.md)。

## 4. Health Agent 数据注入增强

### 变更前

```python
# health_analyze() 仅传递前端请求参数
return agent.analyze(payload)
```

### 变更后

```python
# 自动注入 UserProfile + MealHistory
profile = db.execute(select(UserProfile).where(...)).scalars().first()
meal_history = db.execute(select(MealHistory).where(...)).all()

# 优先使用档案中的身高体重
if profile.height_cm and payload.height_cm == 0:
    payload.height_cm = profile.height_cm

return agent.analyze(payload, meal_history=meal_history, days=7)
```

## 5. 测试覆盖

`tests/test_agent_graphs.py` 新增/更新：

- ✅ `test_recipe_graph_composes_subgraph_context()` — 验证 4 节点流水线：记忆提示注入 + 厨具检查结果写入
- ✅ `test_recipe_graph_inventory_only()` — 验证仅库存模式跳过搜索记忆，结果不含"记忆提示"
