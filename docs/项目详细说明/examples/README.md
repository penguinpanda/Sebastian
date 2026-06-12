# 示例脚本

新人不用读全部源码，运行这些脚本即可理解 Agent 调用链路。

## 前提

```powershell
conda activate ./.conda
# 确保已在项目根目录
```

## 脚本列表

| 脚本 | 说明 | 依赖 |
|------|------|------|
| `call_equipment_agent.py` | 最简单的 Agent（纯规则，无 LLM） | 无 |
| `call_recipe_agent.py` | 完整 Recipe Graph（含 Search + Equipment） | 可选 DEEPSEEK_API_KEY |
| `test_workflow.py` | Mock Service 测试 Graph 节点顺序 | 无 |

## 运行

```powershell
python examples/call_equipment_agent.py
python examples/call_recipe_agent.py
python examples/test_workflow.py
```

## 对应文档

- 请求流程：[docs/04_请求流程分析.md](../docs/04_请求流程分析.md)
- Agent 开发：[docs/05_Agent开发指南.md](../docs/05_Agent开发指南.md)
