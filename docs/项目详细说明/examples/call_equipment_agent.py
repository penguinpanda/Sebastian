#!/usr/bin/env python3
"""示例：直接调用 Equipment Agent（不经过 HTTP）。

用法：
    python examples/call_equipment_agent.py

这是最简单的 Agent 链路：单步 Graph + 纯规则 Service，不依赖 LLM。
"""

from app.schemas.agent_tools import EquipmentCheckRequest
from app.orchestration.agent_graphs import run_equipment_agent


def main() -> None:
    payload = EquipmentCheckRequest(
        equipment_owned=["锅", "平底锅", "砧板"],
        required_equipment=["锅", "烤箱", "砧板", "搅拌器"],
    )

    print("=== Equipment Agent 厨具检查 ===")
    print(f"拥有: {payload.equipment_owned}")
    print(f"需要: {payload.required_equipment}")
    print()

    result = run_equipment_agent(payload)

    print(f"可行: {result.feasible}")
    if result.missing_equipment:
        print(f"缺少: {result.missing_equipment}")
    print(f"建议: {result.suggestion}")


if __name__ == "__main__":
    main()
