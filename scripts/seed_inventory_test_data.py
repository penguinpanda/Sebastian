# -*- coding: utf-8 -*-
"""种子数据注入 — 为「仅使用库存材料生成菜谱」提供验证用测试数据。

用法（需先启动后端 API）：
    ./.conda/python.exe scripts/seed_inventory_test_data.py

覆盖场景：
    1. 正常生成（库存足够）
    2. 多种菜谱可能性
    3. 库存不足无法生成
    4. 确认制作后库存扣减（手动验证）
    5. 边界情况（空库存、数量不足）
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

API_BASE = "http://127.0.0.1:8000/api"

# ═══════════════════════════════════════════════════════════
# 场景定义
# ═══════════════════════════════════════════════════════════

SCENARIO_1 = {
    "user_id": "test-inv-only-001",
    "description": "正常生成 — 库存足够制作多种家常菜",
    "inventory": [
        {"name": "鸡胸肉", "quantity": 500, "unit": "g",
         "expire_date": date.today() + timedelta(days=5), "note": "冷藏"},
        {"name": "西兰花", "quantity": 300, "unit": "g",
         "expire_date": date.today() + timedelta(days=3), "note": "冷藏"},
        {"name": "鸡蛋",    "quantity": 6,   "unit": "个",
         "expire_date": date.today() + timedelta(days=10)},
        {"name": "大米",    "quantity": 2000, "unit": "g",
         "expire_date": date(2026, 12, 31), "note": "主食"},
        {"name": "橄榄油",  "quantity": 500, "unit": "ml",
         "expire_date": date(2027, 1, 1)},
        {"name": "盐",      "quantity": 1000, "unit": "g",
         "expire_date": date(2027, 1, 1)},
        {"name": "酱油",    "quantity": 500, "unit": "ml",
         "expire_date": date(2027, 1, 1)},
        {"name": "大蒜",    "quantity": 200, "unit": "g",
         "expire_date": date.today() + timedelta(days=7)},
        {"name": "姜",      "quantity": 100, "unit": "g",
         "expire_date": date.today() + timedelta(days=8)},
    ],
}

SCENARIO_2 = {
    "user_id": "test-inv-only-002",
    "description": "多种菜谱可能性 — 中西食材混搭",
    "inventory": [
        {"name": "鸡胸肉",  "quantity": 500, "unit": "g",
         "expire_date": date.today() + timedelta(days=5)},
        {"name": "牛肉",    "quantity": 300, "unit": "g",
         "expire_date": date.today() + timedelta(days=4), "note": "牛腩"},
        {"name": "西兰花",  "quantity": 300, "unit": "g",
         "expire_date": date.today() + timedelta(days=3)},
        {"name": "胡萝卜",  "quantity": 200, "unit": "g",
         "expire_date": date.today() + timedelta(days=10)},
        {"name": "土豆",    "quantity": 1000, "unit": "g",
         "expire_date": date.today() + timedelta(days=30)},
        {"name": "洋葱",    "quantity": 300, "unit": "g",
         "expire_date": date.today() + timedelta(days=20)},
        {"name": "西红柿",  "quantity": 400, "unit": "g",
         "expire_date": date.today() + timedelta(days=7)},
        {"name": "鸡蛋",    "quantity": 12, "unit": "个",
         "expire_date": date.today() + timedelta(days=14)},
        {"name": "面粉",    "quantity": 1000, "unit": "g",
         "expire_date": date(2026, 12, 31), "note": "中筋"},
        {"name": "大米",    "quantity": 2000, "unit": "g",
         "expire_date": date(2026, 12, 31)},
    ],
}

SCENARIO_3 = {
    "user_id": "test-inv-only-003",
    "description": "库存不足无法生成 — 仅调料无主食材",
    "inventory": [
        {"name": "盐",   "quantity": 500, "unit": "g",
         "expire_date": date(2027, 1, 1)},
        {"name": "酱油", "quantity": 200, "unit": "ml",
         "expire_date": date(2027, 1, 1)},
    ],
}

SCENARIO_5A = {
    "user_id": "test-inv-only-004",
    "description": "边界情况 — 空库存",
    "inventory": [],
}

SCENARIO_5B = {
    "user_id": "test-inv-only-005",
    "description": "边界情况 — 数量不足（50g 鸡胸肉 + 1 个鸡蛋）",
    "inventory": [
        {"name": "鸡胸肉", "quantity": 50, "unit": "g",
         "expire_date": date.today() + timedelta(days=5), "note": "极少"},
        {"name": "鸡蛋",   "quantity": 1,  "unit": "个",
         "expire_date": date.today() + timedelta(days=10), "note": "仅1个"},
    ],
}

ALL_SCENARIOS = [SCENARIO_1, SCENARIO_2, SCENARIO_3, SCENARIO_5A, SCENARIO_5B]


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def create_item(client: httpx.Client, user_id: str, item: dict) -> bool:
    payload = {
        "user_id": user_id,
        "name": item["name"],
        "quantity": item["quantity"],
        "unit": item["unit"],
        "expire_date": item["expire_date"].isoformat()
        if isinstance(item["expire_date"], date) else item["expire_date"],
        "note": item.get("note", ""),
    }
    try:
        resp = client.post(f"{API_BASE}/inventory", json=payload)
        if resp.status_code == 201:
            return True
        print(f"    !! 创建失败 [{resp.status_code}]: {resp.text[:120]}")
        return False
    except httpx.RequestError as exc:
        print(f"    !! 请求异常: {exc}")
        return False


def seed_scenario(client: httpx.Client, scenario: dict) -> None:
    uid = scenario["user_id"]
    items = scenario.get("inventory", [])
    print(f"\n> {uid} -- {scenario['description']}")
    if not items:
        print("  (空库存，跳过注入)")
        return
    ok = sum(1 for item in items if create_item(client, uid, item))
    print(f"  OK 注入完成: {ok}/{len(items)} 条")


def print_guide() -> None:
    print(f"""
{'=' * 60}
  手动验证 "仅使用库存材料生成菜谱" 指引
{'=' * 60}

1. 正常生成（库存足够）
   curl -X POST {API_BASE}/agents/recipe/recommend-from-inventory -H "Content-Type: application/json" -d '{{"user_id":"test-inv-only-001","meal_type":"dinner","target_calories":600,"available_equipment":["pan","pot","rice_cooker"],"dietary_preferences":["high-protein"]}}'
   预期: 200 + 菜谱，ingredients 全在库存中

2. 多种菜谱可能性
   curl -X POST {API_BASE}/agents/recipe/recommend-from-inventory -H "Content-Type: application/json" -d '{{"user_id":"test-inv-only-002","meal_type":"lunch","target_calories":700,"available_equipment":["pan","pot","oven"],"dietary_preferences":["balanced"]}}'
   预期: 200 + 可选方案多样

3. 库存不足无法生成
   curl -X POST {API_BASE}/agents/recipe/recommend-from-inventory -H "Content-Type: application/json" -d '{{"user_id":"test-inv-only-003","meal_type":"dinner","target_calories":600,"available_equipment":["pan"],"dietary_preferences":[]}}'
   预期: 200 但 missing_ingredients 非空 或 title 为 "无法生成"

4. 确认制作后库存扣减
   先用 test-inv-only-001 获取菜谱，再用返回的 recipe JSON 调用：
   curl -X POST {API_BASE}/meals/confirm -H "Content-Type: application/json" -d '{{"user_id":"test-inv-only-001","recipe":<上一步的recipe JSON>}}'
   预期: 201 + deducted 非空

5a. 边界 -- 空库存
   curl -X POST {API_BASE}/agents/recipe/recommend-from-inventory -H "Content-Type: application/json" -d '{{"user_id":"test-inv-only-004","meal_type":"dinner","target_calories":600,"available_equipment":[],"dietary_preferences":[]}}'
   预期: 400 + "库存为空"

5b. 边界 -- 数量不足
   curl -X POST {API_BASE}/agents/recipe/recommend-from-inventory -H "Content-Type: application/json" -d '{{"user_id":"test-inv-only-005","meal_type":"dinner","target_calories":400,"available_equipment":["pan"],"dietary_preferences":[]}}'
   预期: 200 但 missing_ingredients 非空 或 title 提示无法生成

清理数据
   ./.conda/python.exe scripts/reset_data.py
""")


def main() -> int:
    print("Sebastian 种子数据注入 -- 仅库存菜谱验证")
    print(f"API: {API_BASE}")

    with httpx.Client(timeout=5) as client:
        try:
            resp = client.get(f"{API_BASE}/health")
            if resp.status_code != 200:
                print(f"\n!! API 不可达 (status={resp.status_code})，请先启动后端。")
                return 1
            print(f"OK API 可达: {resp.json()}")
        except httpx.ConnectError:
            print("\n!! 无法连接 API。请先启动:\n   ./.conda/python.exe -m uvicorn app.main:app --reload")
            return 1

    with httpx.Client(timeout=10) as client:
        for s in ALL_SCENARIOS:
            seed_scenario(client, s)

    print_guide()
    return 0


if __name__ == "__main__":
    sys.exit(main())