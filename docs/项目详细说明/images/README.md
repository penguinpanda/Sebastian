# 架构图资源

本目录存放项目架构的可视化图表。当前提供 Mermaid 源码，可导出为 PNG 供文档引用。

## 文件说明

| 文件 | 内容 | 状态 |
|------|------|------|
| `architecture.png` | 系统分层架构图 | 待导出 |
| `request_flow.png` | Recipe 请求流程时序图 | 待导出 |
| `agent_graph.png` | Agent 协作关系图 | 待导出 |
| `database.png` | 数据库 ER 图 | 待导出 |

## Mermaid 源码

### architecture — 系统分层

```mermaid
flowchart TB
    Client[Frontend / API Client] --> API[FastAPI API Layer]
    API --> Agent[Agent Layer]
    API --> ServiceDirect[Service Layer Direct]

    Agent --> Orch[Orchestration LangGraph]
    Orch --> Service[Service Layer]
    ServiceDirect --> Repo[Repository Layer]

    Service --> Repo
    Service --> LLM[LLM DeepSeek]
    Service --> ES[Elasticsearch]
    Repo --> PG[(PostgreSQL)]
    Service --> Redis[(Redis)]
```

### request_flow — Recipe 推荐时序

```mermaid
sequenceDiagram
    participant U as Client
    participant API as agent_tools.py
    participant G as recipe_graph
    participant S as SearchService
    participant R as RecipeService
    participant E as EquipmentService
    participant LLM as DeepSeek

    U->>API: POST /agents/recipe/recommend
    API->>G: run_recipe_agent()
    G->>S: collect_context
    S-->>G: search_result
    G->>R: compose
    R->>LLM: chat_json()
    LLM-->>R: recipe JSON
    G->>E: check_equipment
    E-->>G: equipment_result
    G->>G: finalize
    G-->>API: RecipeRecommendResponse
    API-->>U: JSON
```

### agent_graph — Agent 协作

```mermaid
flowchart TD
    RA[Recipe Agent] --> SA[Search Agent]
    RA --> EA[Equipment Agent]
    RA --> IS[Inventory Service]

    IA[Inventory Agent Chat] --> IG[Inventory Graph]
    IG --> LLM[DeepSeek LLM]

    HA[Health Agent]
    SA2[Search Agent Standalone]

    style RA fill:#e1f5fe
    style IA fill:#e1f5fe
    style HA fill:#f3e5f5
    style SA fill:#f3e5f5
    style SA2 fill:#f3e5f5
    style EA fill:#f3e5f5
```

### database — ER 关系

```mermaid
erDiagram
    inventories ||--o{ inventory_transactions : has
    agent_tasks ||--o{ tool_call_logs : has

    inventories {
        uuid id PK
        string name
        numeric quantity
        string unit
        date expire_date
    }

    inventory_transactions {
        uuid id PK
        uuid inventory_id FK
        string action
        numeric amount
    }

    agent_tasks {
        uuid id PK
        string user_id
        string task_type
        string status
        json input_payload
        json output_payload
    }

    tool_call_logs {
        uuid id PK
        uuid task_id FK
        string trace_id
        string tool_name
        int latency_ms
    }
```

## 导出 PNG

使用 [Mermaid Live Editor](https://mermaid.live) 或 VS Code Mermaid 插件导出：

1. 复制上方 Mermaid 源码
2. 粘贴到编辑器
3. 导出 PNG/SVG
4. 保存到本目录

## 引用方式

在 Markdown 文档中：

```markdown
![系统架构](./images/architecture.png)
```

或使用 Mermaid 内联（GitHub / 部分 Markdown 渲染器支持）：

````markdown
```mermaid
flowchart TB
    ...
```
````
