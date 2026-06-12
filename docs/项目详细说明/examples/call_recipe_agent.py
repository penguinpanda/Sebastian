#!/usr/bin/env python3
"""示例：直接调用 Recipe Agent（不经过 HTTP）。

用法：
    python examples/call_recipe_agent.py

前提：
    - 已安装项目依赖（pip install -e .[dev]）
    - 可选：.env 中设置 DEEPSEEK_API_KEY（无 Key 时使用模板降级）
"""

from app.schemas.agent_tools import RecipeRecommendRequest
from app.orchestration.agent_graphs import run_recipe_agent


def main() -> None:
    payload = RecipeRecommendRequest(
        user_id="demo",
        meal_type="dinner",
        target_calories=600,
        available_equipment=["锅", "平底锅", "砧板"],
        dietary_preferences=["少油", "高蛋白"],
    )

    print("=== Recipe Agent 推荐 ===")
    print(f"输入: {payload.meal_type}, 目标 {payload.target_calories} kcal")
    print()

    result = run_recipe_agent(payload)

    print(f"标题: {result.title}")
    print(f"理由: {result.rationale}")
    print(f"预估热量: {result.estimated_calories} kcal")
    print(f"步骤:")
    for i, step in enumerate(result.steps, 1):
        print(f"  {i}. {step}")
    print(f"所需厨具: {result.required_equipment}")
    print(f"可行: {result.feasible}")
    if result.missing_equipment:
        print(f"缺少厨具: {result.missing_equipment}")
    if result.missing_ingredients:
        print(f"缺少食材: {result.missing_ingredients}")


if __name__ == "__main__":
    main()
