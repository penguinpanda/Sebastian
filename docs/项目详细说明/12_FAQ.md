# FAQ 常见问题

> 新人高频问题与排查路径。

---

## Agent 相关

### Q: 为什么 RecipeAgent 没有调用 EquipmentAgent？

**A:** Recipe 的厨具校验在 Orchestration 层，不在 Agent 类中。检查 `app/orchestration/agent_graphs.py` 中 `_build_recipe_graph()` 是否包含：

```
collect_context → compose → check_equipment → finalize
```

如果 `check_equipment` 节点被删除或边接错，厨具校验不会执行。

---

### Q: Agent Chat 返回 "I'm not sure how to help with that"

**A:** 这是 Inventory Graph 的 fallback 回复。原因：

1. LLM 意图识别失败（检查 `DEEPSEEK_API_KEY`）
2. 用户输入为空
3. LLM 返回的 intent 为 `unknown`

排查：`app/orchestration/nodes.py` → `classify_intent()`，查看 WARNING 日志。

---

### Q: Recipe 推荐返回的是模板内容，不是 LLM 生成的

**A:** 正常降级行为。触发条件：

1. `DEEPSEEK_API_KEY` 未设置
2. LLM 调用失败（超时、无效 JSON 等）

日志会有：`Recipe LLM generation failed, fallback to template`

解决：设置有效的 `DEEPSEEK_API_KEY`。

---

### Q: 新增 Agent 后 API 404

**A:** 检查：

1. 路由是否在 `app/api/router.py` 中注册
2. 路由前缀是否正确（Agent Tools 在 `/api/agents/` 下）
3. 服务是否重启

---

## 架构相关

### Q: Agent 和 Service 的区别是什么？

**A:**

| | Agent | Service |
|---|-------|---------|
| 位置 | `app/agents/` | `app/services/` |
| 职责 | 薄门面，委托给 Graph | 业务逻辑 |
| 代码量 | 通常 < 20 行 | 实际业务代码 |
| 测试 | 通过 Graph 集成测试 | 可独立单元测试 |

Agent 是"入口"，Service 是"大脑"。

---

### Q: 什么时候用 Graph，什么时候直接调 Service？

**A:**

- **单步 Agent**（Health、Equipment、Search）：Graph 是单节点包装，保持架构一致性
- **多步 Agent**（Recipe）：Graph 控制节点顺序和状态传递
- **CRUD API**（Inventory）：直接调 Service，不需要 Graph
- **Chat API**：Graph 做意图路由

---

### Q: 为什么有两套 orchestration 文件？

**A:**

- `graph.py` — Inventory 聊天主图（自然语言 → 意图 → 回复）
- `agent_graphs.py` — 专用 Agent 子图（结构化 API 调用）

历史原因 + 职责分离。后续可能统一，当前保持两个文件。

---

## 数据相关

### Q: 库存数据存在哪里？

**A:** PostgreSQL `inventories` 表。通过 `InventoryService` → `PostgresInventoryRepository` 访问。

不在 Elasticsearch 中。

---

### Q: 记忆搜索和 Agent Search 有什么区别？

**A:**

- `GET /api/search/memory` — 直接调 `SearchService`，返回原始检索结果
- `POST /api/agents/search/answer` — 调 `SearchAgentService`，包装为摘要 + 证据列表

Recipe Graph 内部调用的是后者。

---

### Q: 为什么 readiness 返回 503？

**A:** 某个依赖不可用。检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/dependencies
```

常见原因：PostgreSQL / Redis / Elasticsearch 容器未启动。

---

## LLM 相关

### Q: 没有 DeepSeek API Key 能运行吗？

**A:** 可以。影响：

- Recipe 推荐 → 模板降级（仍可用）
- Inventory Chat → 意图识别失败 → fallback 回复
- 其他 Agent（Health、Equipment）→ 不依赖 LLM，正常

---

### Q: 如何切换 LLM 模型？

**A:** 修改 `.env`：

```env
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

客户端兼容 OpenAI Chat Completions 格式。

---

## 开发相关

### Q: 修改菜谱生成逻辑应该改哪个文件？

**A:**

| 改什么 | 文件 |
|--------|------|
| 菜谱内容 / Prompt | `services/recipe_agent_service.py` |
| 流程（加节点） | `orchestration/agent_graphs.py` |
| API 参数 | `schemas/agent_tools.py` + `api/routes/agent_tools.py` |
| 返回字段 | `schemas/agent_tools.py` |

---

### Q: 如何运行单个测试？

**A:**

```powershell
.\.conda\python.exe -m pytest tests/test_agent_graphs.py -v -k recipe
.\.conda\python.exe -m pytest tests/test_inventory_api.py -v
```

---

### Q: 前端连不上后端？

**A:** 检查：

1. `frontend/.env.development` → `VITE_API_BASE_URL=http://127.0.0.1:8000/api`
2. `.env` → `CORS_ORIGINS` 包含 `http://localhost:5173`
3. 后端是否在 8000 端口运行

---

## 部署相关

### Q: Docker Compose 和本地开发有什么区别？

**A:**

| | 本地开发 | Docker Compose |
|---|---------|----------------|
| API | 手动 uvicorn | 容器自动启动 |
| 热重载 | `--reload` | `--reload` |
| 迁移 | 手动 alembic | migrate 服务自动执行 |
| Celery | 手动启动 | 容器自动启动 |
| 适用 | 日常开发 | 验收 / 演示 |

---

### Q: 数据库迁移失败怎么办？

**A:**

1. 确认 PostgreSQL 容器健康：`docker compose ps`
2. 确认 `DATABASE_URL` 正确
3. 查看迁移历史：`alembic current`
4. 如需重置（**开发环境**）：`docker compose down -v` 后重新启动

---

## 更多帮助

- 调试流程：[10_调试指南.md](./10_调试指南.md)
- 架构说明：[02_项目架构.md](./02_项目架构.md)
- 请求流程：[04_请求流程分析.md](./04_请求流程分析.md)
