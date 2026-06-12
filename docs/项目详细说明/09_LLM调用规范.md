# LLM 调用规范

> AI 项目的核心基础设施：Prompt、模型、超时、重试与降级。

## 目录结构

```
app/llm/
├── client.py          # DeepSeek HTTP 客户端
├── prompts.py         # Inventory 聊天 Prompt 模板
└── output_parser.py   # LLM JSON 输出解析
```

部分 Agent 的 Prompt 内联在 Service 中（如 Recipe），后续可统一到 `prompts.py`。

## 客户端

`app/llm/client.py` 提供 `DeepSeekClient`：

```python
from app.llm.client import get_llm_client

client = get_llm_client()
text = client.chat(messages, temperature=0.7, max_tokens=1024)
data = client.chat_json(messages, temperature=0.3, max_tokens=1024)
```

### 单例模式

`get_llm_client()` 返回进程内单例，避免重复创建 HTTP 连接。

## 配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DEEPSEEK_API_KEY` | （空） | API 密钥，空则 LLM 功能降级 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `LLM_TIMEOUT_MS` | `5000` | 单次请求超时（毫秒） |
| `LLM_RETRY_MAX` | `2` | 最大重试次数 |

配置定义：`app/core/config.py`

## 模型切换

修改 `.env` 即可：

```env
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

如需切换到其他 OpenAI 兼容 API，修改 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_API_KEY`。

客户端代码无需改动（基于 OpenAI Chat Completions 格式）。

## Prompt 维护

### Inventory 聊天 Prompt

位置：`app/llm/prompts.py`

```python
SYSTEM_INVENTORY = """你是 Sebastian，一位个人厨房与生活助手..."""

def build_inventory_messages(user_input: str, context: str = "") -> list[dict]:
    ...
```

使用方：`app/orchestration/nodes.py` → `classify_intent()`

### Recipe 生成 Prompt

位置：`app/services/recipe_agent_service.py` → `_recommend_with_llm()`

内联在 Service 中，要求 LLM 返回 JSON：

```python
messages = [
    {"role": "system", "content": "你是一名营养导向的菜谱规划助手..."},
    {"role": "user", "content": f"用户ID：{payload.user_id}..."},
]
raw = get_llm_client().chat_json(messages, temperature=0.4, max_tokens=600)
```

### Prompt 编写规范

1. System Prompt 明确输出格式（JSON Schema 或字段列表）
2. 要求 LLM 仅返回 JSON，不含 Markdown 围栏
3. User Prompt 包含所有必要上下文（用户 ID、偏好、库存等）
4. 使用中文作为默认输出语言

## Token 限制

当前各调用点的 `max_tokens` 设置：

| 调用点 | max_tokens | temperature |
|--------|-----------|-------------|
| Inventory 意图识别 | 1024（默认） | 0.2 |
| Recipe 生成 | 600 | 0.4 |
| 通用聊天 | 1024（默认） | 0.7 |

调整原则：
- 结构化 JSON 输出：较低 temperature（0.2–0.4）
- 自然语言回复：较高 temperature（0.7）
- 根据实际输出长度调整 max_tokens，避免截断

## 重试策略

`DeepSeekClient.chat()` 内置指数退避重试：

```
attempt 0 → 失败 → 等待 1s → 重试
attempt 1 → 失败 → 等待 2s → 重试
attempt 2 → 失败 → 抛出 LLMError
```

仅对网络超时和网络错误重试，不对 401/429/500 等业务错误重试。

配置：`LLM_RETRY_MAX=2`（共 3 次尝试）

## 降级策略

### Recipe Agent

```python
if settings.deepseek_api_key:
    llm_result = self._recommend_with_llm(payload)
    if llm_result is not None:
        return llm_result
return self._recommend_with_template(payload)  # 模板降级
```

无 API Key 或 LLM 失败时，使用基于库存数量的模板生成。

### Inventory Chat

```python
except Exception as exc:
    return {**state, "intent": "unknown", "error_state": str(exc)}
```

LLM 失败时走 fallback 节点，返回兜底文案。

### Search Agent

```python
except Exception:
    return SearchAnswerResponse(summary="记忆检索服务暂时不可用...")
```

Elasticsearch 不可用时优雅降级。

## 错误处理

`app/core/errors.py` 定义 `LLMError`：

| 场景 | 行为 |
|------|------|
| 401 无效 Key | 立即抛 LLMError |
| 429 限流 | 立即抛 LLMError |
| 5xx 服务端错误 | 立即抛 LLMError |
| 无效 JSON 响应 | 抛 LLMError（含原始文本前 400 字符） |
| 网络超时 | 重试后抛 LLMError |

Service 层捕获 LLMError 并决定降级，不向上传播到 API 层（除非无法降级）。

## 输出解析

`app/llm/output_parser.py` 解析 Inventory 意图 JSON：

```python
parsed = parse_inventory_response(raw)
# → IntentResponse(intent, action, parameters, reply)
```

新增 Agent 如需 JSON 解析，可在此添加或使用 Pydantic `model_validate()`。

## 调试 LLM 调用

1. 确认 API Key：`echo $env:DEEPSEEK_API_KEY`
2. 调高超时：`LLM_TIMEOUT_MS=15000`
3. 查看日志：LLM 失败会输出 `WARNING` 级别日志
4. 单独测试：

```python
from app.llm.client import get_llm_client
client = get_llm_client()
print(client.chat([{"role": "user", "content": "你好"}]))
```

5. 使用 trace_id 关联请求日志

## 最佳实践

- [ ] Prompt 变更后跑相关测试
- [ ] 新 Agent 的 LLM 调用放在 Service 层
- [ ] 必须有降级路径（无 Key 时不应 500）
- [ ] JSON 输出使用 `chat_json()` + Pydantic 校验
- [ ] 不在 Prompt 中硬编码敏感信息
