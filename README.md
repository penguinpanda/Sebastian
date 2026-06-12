# Sebastian - 个人生活与厨房 AI 助手系统

Sebastian 是一个以库存管理与多 Agent 协作为核心的个人 AI 系统，包含后端 API、异步任务与前端界面。

## 文档入口

**新人入门：** [docs/项目详细说明/README.md](docs/项目详细说明/README.md)（推荐从这里开始）

- [docs/README.md](docs/README.md)
- [docs/00_项目介绍.md](docs/00_项目介绍.md)
- [docs/04_请求流程分析.md](docs/04_请求流程分析.md)
- [examples/](examples/) — 示例脚本
- [CONTRIBUTING.md](CONTRIBUTING.md) — 开发规范
- [docs/使用指南.md](docs/使用指南.md)
- [docs/部署完整指南.md](docs/部署完整指南.md)
- [docs/测试与质量.md](docs/测试与质量.md)
- [docs/可观测性与监控.md](docs/可观测性与监控.md)
- [docs/设计文档.md](docs/设计文档.md)
- [docs/开发进度与待办.md](docs/开发进度与待办.md)
- [docs/前端开发进度与待办.md](docs/前端开发进度与待办.md)
- [docs/项目开发现状总览.md](docs/项目开发现状总览.md)

## 快速启动

```powershell
conda create -p ./.conda python=3.12 -y
conda activate ./.conda
python -m pip install -e .[dev]
Copy-Item .env.example .env
docker compose up -d postgres redis
alembic upgrade head
.\.conda\python.exe -m uvicorn app.main:app --reload
```

前端:

```powershell
cd frontend
npm install
npm run dev
```

## Dev Ready 验收入口

1. 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/health/readiness
```

2. 回归测试

```powershell
make test-unit
make integration
```

3. 关键链路

- Inventory: 创建、查询、调整
- Agent: 聊天、任务状态、队列状态
- Search: memory 写入与检索
- MCP: tools 与 invoke
- Celery: 触发扫描与任务历史查询

## 主要技术栈

- FastAPI
- SQLAlchemy + PostgreSQL
- Redis
- Elasticsearch
- Celery
- LangGraph
- DeepSeek API（默认 `deepseek-chat`）
- React + TypeScript + Vite

## 许可证

MIT License

