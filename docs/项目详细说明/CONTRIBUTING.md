# Contributing 开发规范

## 新增功能必须包含

| 组件 | 说明 | 目录 |
|------|------|------|
| Schema | 请求/响应 Pydantic 模型 | `app/schemas/` |
| Service | 业务逻辑 | `app/services/` |
| Agent | 薄门面（如涉及 Agent） | `app/agents/` |
| Graph | LangGraph 编排（如涉及 Agent） | `app/orchestration/` |
| API | HTTP 路由 | `app/api/routes/` |
| Test | 单元测试 | `tests/` |

## 分层规则

```
API → Agent → Orchestration → Service → Repository → Database
```

**禁止跨层调用：**

- Agent 不能直接访问 Repository / 数据库
- Service 不能 import FastAPI
- Repository 不能包含业务规则
- API 路由不能包含业务计算

## 代码风格

- 遵循项目现有命名和结构
- 方法签名使用 Pydantic Schema，不用裸 dict
- 依赖通过构造函数注入，便于测试
- LLM 调用必须有降级路径
- 不添加无必要的注释

## 测试要求

```powershell
# 新增代码后运行
make test-unit

# 涉及 DB/Redis/ES 的改动
make integration
```

- Service 层必须有单元测试
- API 层推荐集成测试
- Graph 测试使用 Mock Service 注入（参考 `tests/test_agent_graphs.py`）

## 数据库变更

1. 修改 `app/models/`
2. 生成迁移：`alembic revision --autogenerate -m "description"`
3. 检查迁移 SQL
4. 更新 `docs/08_数据库设计.md`

## 文档同步

接口或架构变更后，同步更新：

- 对应编号文档（`docs/0X_*.md`）
- 如涉及 API 变更：`docs/07_API开发指南.md` 和 `docs/使用指南.md`

## 提交前检查

- [ ] 单元测试通过
- [ ] 无 secrets 提交（`.env` 不入库）
- [ ] Schema / Service / Test 齐全
- [ ] 分层边界未违反
- [ ] 相关文档已更新

## 新人入门

请先阅读 [docs/项目详细说明/README.md](docs/项目详细说明/README.md) 中的推荐阅读顺序。
