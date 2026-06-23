# API 变更汇总

> 更新时间: 2026-06-12

本文档列出 2026-06-12 所有新增和变更的 API 端点。

## 1. 新增端点

| 方法 | 路径 | 说明 | 状态码 |
|------|------|------|--------|
| `POST` | `/api/agents/recipe/recommend-from-inventory` | 仅使用库存材料生成菜谱 | 200 / 400 / 503 |
| `POST` | `/api/meals/confirm` | 确认制作菜谱 → 扣库存 → 写历史 | 201 |
| `GET` | `/api/meals/history` | 查询饮食历史 | 200 |
| `POST` | `/api/meals/{meal_id}/rollback` | 回退餐食（恢复库存） | 200 / 404 / 409 |
| `POST` | `/api/conversations/save` | 保存/覆盖当日对话 | 200 |
| `GET` | `/api/conversations` | 加载指定日期对话 | 200 |
| `GET` | `/api/conversations/dates` | 获取对话日期列表 | 200 |
| `POST` | `/api/profile` | 创建/更新用户健康档案 | 200 |
| `GET` | `/api/profile` | 查询用户健康档案 | 200 / 404 |
| `GET` | `/api/recipes` | 搜索菜谱库 | 200 |
| `GET` | `/api/recipes/top` | 最常制作 Top N | 200 |

## 2. 变更端点

| 方法 | 路径 | 变更说明 |
|------|------|----------|
| `POST` | `/api/agents/health/analyze` | 自动注入 `UserProfile` + `MealHistory`，优先使用档案中的身高体重 |
| `POST` | `/api/agents/recipe/recommend` | Recipe Graph 增强：新增厨具检查节点，响应增加 `feasible` + `missing_equipment` 字段 |

## 3. 端点详情

### 3.1 仅库存菜谱 `POST /api/agents/recipe/recommend-from-inventory`

```
请求: InventoryOnlyRecipeRequest
响应: RecipeRecommendResponse
```

- [详细文档](./仅库存菜谱生成.md)

### 3.2 饮食确认 `POST /api/meals/confirm`

```
请求: { user_id, recipe: RecipeRecommendResponse }
响应: { meal_id, status, deducted[], missing[], errors[] }
```

- [详细文档](./饮食确认与数据闭环.md)

### 3.3 饮食历史 `GET /api/meals/history`

```
参数: user_id (必填), days (默认 7)
响应: { meals: [...] }
```

### 3.4 回退餐食 `POST /api/meals/{meal_id}/rollback`

回退已确认餐食的库存扣减。约束：只能回退未回退过的记录。

### 3.5 对话保存 `POST /api/conversations/save`

```
请求: { user_id, date, messages[] }
响应: { id, user_id, date, messages[], last_active_at }
```

同一日期重复保存会覆盖。参见 [对话持久化](./对话持久化.md)。

### 3.6 对话加载 `GET /api/conversations`

```
参数: user_id (必填), date (必填, YYYY-MM-DD)
响应: { id, user_id, date, messages[], last_active_at }
无记录时 messages 为空数组
```

### 3.7 对话日期列表 `GET /api/conversations/dates`

```
参数: user_id (必填)
响应: { dates: ["2026-06-12", ...] }
```

### 3.8 用户档案 `POST /api/profile`

```
请求: { user_id, age?, gender?, height_cm?, weight_kg?, activity_level?, health_goal? }
响应: 完整 UserProfile
```

Upsert 语义。参见 [用户健康档案](./用户健康档案.md)。

### 3.9 用户档案查询 `GET /api/profile`

```
参数: user_id (必填)
响应: UserProfile 或 {"detail": "not_found"}
```

### 3.10 菜谱搜索 `GET /api/recipes`

```
参数: user_id (必填), query (可选), sort (times_made/calories/recent), limit (1-100)
响应: { recipes: RecipeLibraryItem[], count: int }
```

参见 [菜谱库](./菜谱库.md)。

### 3.11 热门菜谱 `GET /api/recipes/top`

```
参数: user_id (必填), limit (1-50, 默认 10)
响应: { recipes: RecipeLibraryItem[], count: int }
```

## 4. 响应模型新增字段

### `RecipeRecommendResponse`

| 字段 | 类型 | 说明 |
|------|------|------|
| `ingredients` | `list[RecipeIngredient]` | 🆕 结构化食材列表 `{name, amount, unit}` |
| `required_equipment` | `list[str]` | 🆕 制作所需厨具 |
| `feasible` | `bool` | 🆕 厨具是否满足，默认 true |
| `missing_equipment` | `list[str]` | 🆕 缺少的厨具 |

### `RecipeIngredient`（新模型）

```python
class RecipeIngredient(BaseModel):
    name: str    # 食材名，1-120 字符
    amount: float  # 用量，>0
    unit: str    # 单位，1-20 字符 (g/ml/个)
```
