# Sebastian — 个人 AI 生活助手系统（简历项目描述）

---

## 项目概述

Sebastian 是一个面向日常生活场景的个人 AI Agent 后端系统。  
项目从零开始设计与实现，核心目标是将食材库存管理、菜谱推荐与健康分析整合在一个可持续演进的智能 Agent 平台中。  
当前已交付可运行的后端 MVP，具备完整的领域分层、持久化存储、数据库迁移、容器化部署与多层次测试体系。

---

## 技术栈

| 类别 | 技术选型 |
|---|---|
| 后端框架 | FastAPI 0.115 |
| 语言 | Python 3.12 |
| 数据库 | PostgreSQL 16 + SQLAlchemy 2.0 |
| 数据库迁移 | Alembic |
| 数据驱动 | psycopg（psycopg3 binary） |
| 数据校验 | Pydantic v2 |
| 缓存/队列 | Redis（预留接口） |
| 容器化 | Docker、Docker Compose |
| 测试框架 | pytest + pytest-asyncio |
| HTTP 客户端 | httpx（ASGITransport 测试模式） |
| 环境管理 | conda（项目独立 .conda 环境） |
| 构建入口 | GNU Make |

---

## 核心实现

### 分层架构

```
Client
  └── FastAPI (HTTP Router)
        └── Service Layer (业务逻辑 + 输入校验)
              └── Repository Protocol (接口抽象)
                    ├── PostgresInventoryRepository (生产实现)
                    └── InMemoryInventoryRepository (测试替身)
```

- 依赖注入链：`get_db_session → PostgresInventoryRepository → InventoryService → FastAPI 路由`
- 数据库引擎懒加载（`lru_cache`），测试阶段无需真实数据库也可跑通 API 冒烟测试

### 库存管理 API

完整实现了以下 RESTful 接口：

| 方法 | 路径 | 功能 |
|---|---|---|
| POST | /api/inventory | 创建库存 |
| GET | /api/inventory | 列表查询 |
| GET | /api/inventory/{id} | 详情查询 |
| PATCH | /api/inventory/{id}/adjust | 库存增减（写入流水） |
| GET | /api/inventory/alerts/expiring | 临期提醒 |
| GET | /api/inventory/summary | 汇总统计 |
| GET | /api/health | 健康检查 |

### 数据库事务与流水日志

每次库存调整（入库/出库）自动写入 `inventory_transactions` 表，记录动作类型、变更量与备注，支持后续的操作审计与趋势分析。

### 容器化部署

Docker Compose 编排四个服务：
- `postgres`：带 healthcheck，确保就绪后再启动迁移
- `migrate`：自动执行 `alembic upgrade head`，依赖 `postgres` healthy 状态
- `api`：依赖 `migrate` 完成后启动，注入容器内数据库地址
- `redis`：预留缓存与任务队列接口

---

## 测试体系

采用四层测试结构，覆盖不同环境与粒度：

| 测试类型 | 文件 | 说明 |
|---|---|---|
| API 冒烟测试 | test_health.py / test_inventory_api.py | httpx AsyncClient + ASGITransport，依赖覆盖注入 InMemory 实现，无需真实数据库 |
| 仓储单元测试 | test_postgres_inventory_repository.py | SQLite 内存数据库，验证正常路径与负库存异常、事务流水记录 |
| 容器集成测试 | test_postgres_container_integration.py | 自动拉起真实 PostgreSQL Docker 容器，执行 Alembic 迁移，验证完整读写链路，环境不满足时自动跳过 |

**测试结果：** 5 tests collected，4 passed，1 skipped（集成测试在 Docker 不可用时自动降级）

---

## 工程规范

- **配置管理**：pydantic-settings 统一读取环境变量，容器内外通过 `DATABASE_URL` 切换数据库地址
- **异常分层**：`SebastianError → NotFoundError / ValidationError`，HTTP 层统一转换为标准 4xx 响应
- **仓储接口化**：`InventoryRepository` Protocol 解耦业务逻辑与存储实现，便于替换或扩展
- **Make 入口统一**：`make test / make test-unit / make integration` 均通过 [scripts/run_pytest_conda.py](../scripts/run_pytest_conda.py) 驱动，确保所有命令使用同一 conda 环境

---

## 项目规模

| 维度 | 数据 |
|---|---|
| 代码模块 | 17 个 Python 文件 |
| API 接口 | 7 个 REST 端点 |
| 数据库表 | 2 张（inventories + inventory_transactions） |
| 测试用例 | 5 个（覆盖 API / 仓储 / 容器集成三层） |
| 容器服务 | 4 个（postgres / redis / migrate / api） |

---

## 待扩展方向

- **LangGraph 编排层**：实现意图路由与多 Agent 协同（Recipe / Health / Search Agent）
- **DeepSeek API 接入**：统一 LLM 客户端，deepseek-chat 单模型策略
- **Elasticsearch 语义检索**：长期记忆与偏好向量化召回
- **Celery 异步任务**：库存过期扫描与定时提醒
- **MCP 工具协议层**：标准化外部工具接入

---

## 可量化亮点（面试描述建议）

- 从零设计并实现 FastAPI 后端，落地仓储接口 + 双实现（内存 / PostgreSQL），支持无数据库环境下的 CI 冒烟测试
- 设计并实现三层测试体系（API / 仓储 / 容器集成），集成测试自动拉起 PostgreSQL 容器并执行迁移，覆盖完整读写链路
- 通过 Docker Compose + healthcheck + 服务启动依赖链，实现"一条命令冷启动全栈"
- 统一工程入口（Makefile + Python 启动器），消除多环境/多工具带来的测试行为漂移
