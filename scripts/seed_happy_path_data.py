# -*- coding: utf-8 -*-
"""种子数据注入 — 库存 + 菜谱推荐 Happy Path 全链路正常流程验证。

用法（需先启动后端 API）：
    ./.conda/python.exe scripts/seed_happy_path_data.py

与 seed_inventory_test_data.py 的区别：
    - 只覆盖 Happy Path（正常流程），不包含边界/异常场景
    - 注入完整用户健康档案，用于验证 RecipeAgent 的 _build_profile_context
    - 库存食材种类更丰富（12+ 种常用中式食材），确保 LLM 能生成多种菜谱
    - 覆盖完整链路：档案 → 库存 → 菜谱推荐 → 仅库存菜谱 → 确认制作

验证场景：
    1. 用户档案已创建且可查询
    2. 库存正常注入，数量充足
    3. 完整菜谱推荐（走搜索记忆 + 厨具检查 + LLM 完整图）
    4. 仅库存菜谱推荐（跳过搜索/厨具，直接 LLM 约束）
    5. 确认制作 → 库存扣减 → 饮食历史写入 → 菜谱入库
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
# 场景定义：Happy Path 用户
# ═══════════════════════════════════════════════════════════

SCENARIO = {
    "user_id": "test-happy-001",
    "description": "Happy Path — 完整用户档案 + 丰富库存，覆盖全链路正常流程",

    # ── 用户健康档案 ──
    "profile": {
        "classification": "single_male",       # 单身男性 → LLM 推荐单人份
        "age": 28,
        "gender": "male",
        "height_cm": 178.0,
        "weight_kg": 82.0,
        "activity_level": "medium",             # 中等活动量
        "health_goal": "lose_weight",           # 减重目标
        "preferences": {
            "dietary": ["高蛋白", "低油", "少盐", "低碳水"],
            "lifestyle": ["早起", "工作日晚间做饭"],
            "cuisine": ["中式家常", "川菜", "粤菜"],
            "equipment": ["炒锅", "汤锅", "电饭煲", "蒸锅", "平底锅", "空气炸锅", "菜刀", "砧板", "微波炉"],
            "free_text": "偏好快手菜，30分钟内完成。周末会尝试复杂菜式。不喜欢甜味主菜。",
        },
    },

    # ── 库存食材（12+ 种，数量充足，过期日合理）──
    "inventory": [
        # ── 蛋白质类 ──
        {"name": "鸡胸肉", "quantity": 800, "unit": "g",
         "expire_date": date.today() + timedelta(days=5), "note": "冷藏，2块"},
        {"name": "鸡蛋", "quantity": 12, "unit": "个",
         "expire_date": date.today() + timedelta(days=14), "note": "冷藏"},
        {"name": "牛肉", "quantity": 400, "unit": "g",
         "expire_date": date.today() + timedelta(days=3), "note": "牛腱子，冷藏"},
        {"name": "虾仁", "quantity": 300, "unit": "g",
         "expire_date": date.today() + timedelta(days=2), "note": "冷冻"},

        # ── 蔬菜类 ──
        {"name": "西兰花", "quantity": 350, "unit": "g",
         "expire_date": date.today() + timedelta(days=4), "note": "冷藏"},
        {"name": "西红柿", "quantity": 500, "unit": "g",
         "expire_date": date.today() + timedelta(days=6), "note": "4个"},
        {"name": "胡萝卜", "quantity": 300, "unit": "g",
         "expire_date": date.today() + timedelta(days=10), "note": "3根"},
        {"name": "洋葱", "quantity": 400, "unit": "g",
         "expire_date": date.today() + timedelta(days=14), "note": "2个"},
        {"name": "青椒", "quantity": 200, "unit": "g",
         "expire_date": date.today() + timedelta(days=5), "note": "2个"},
        {"name": "白菜", "quantity": 600, "unit": "g",
         "expire_date": date.today() + timedelta(days=7), "note": "半颗"},

        # ── 主食类 ──
        {"name": "大米", "quantity": 3000, "unit": "g",
         "expire_date": date(2027, 6, 1), "note": "五常大米"},
        {"name": "面粉", "quantity": 1500, "unit": "g",
         "expire_date": date(2027, 3, 1), "note": "中筋面粉"},

        # ── 调料类 ──
        {"name": "橄榄油", "quantity": 750, "unit": "ml",
         "expire_date": date(2027, 1, 1), "note": "烹饪用"},
        {"name": "盐", "quantity": 1000, "unit": "g",
         "expire_date": date(2027, 12, 31)},
        {"name": "酱油", "quantity": 500, "unit": "ml",
         "expire_date": date(2027, 6, 1), "note": "生抽"},
        {"name": "料酒", "quantity": 500, "unit": "ml",
         "expire_date": date(2027, 6, 1)},
        {"name": "大蒜", "quantity": 200, "unit": "g",
         "expire_date": date.today() + timedelta(days=15)},
        {"name": "姜", "quantity": 150, "unit": "g",
         "expire_date": date.today() + timedelta(days=10)},
        {"name": "干辣椒", "quantity": 100, "unit": "g",
         "expire_date": date(2027, 12, 31), "note": "调料"},
    ],

    # ── 常用厨具（item_type=equipment，前端「厨具」页展示）──
    "equipment": [
        {"name": "炒锅", "quantity": 1, "unit": "个", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "不粘锅，32cm"},
        {"name": "汤锅", "quantity": 1, "unit": "个", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "不锈钢，24cm"},
        {"name": "电饭煲", "quantity": 1, "unit": "个", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "3L"},
        {"name": "蒸锅", "quantity": 1, "unit": "个", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "双层"},
        {"name": "平底锅", "quantity": 1, "unit": "个", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "28cm"},
        {"name": "空气炸锅", "quantity": 1, "unit": "个", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "4.5L"},
        {"name": "菜刀", "quantity": 1, "unit": "把", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "中式菜刀"},
        {"name": "砧板", "quantity": 1, "unit": "块", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "竹制"},
        {"name": "微波炉", "quantity": 1, "unit": "个", "item_type": "equipment",
         "expire_date": date(2030, 1, 1), "note": "20L"},
    ],
}


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def create_profile(client: httpx.Client, user_id: str, profile: dict) -> bool:
    """POST /api/profile 创建或更新用户健康档案。"""
    payload = {
        "user_id": user_id,
        "classification": profile.get("classification"),
        "age": profile.get("age"),
        "gender": profile.get("gender"),
        "height_cm": profile.get("height_cm"),
        "weight_kg": profile.get("weight_kg"),
        "activity_level": profile.get("activity_level"),
        "health_goal": profile.get("health_goal"),
        "preferences": profile.get("preferences", {}),
    }
    try:
        resp = client.post(f"{API_BASE}/profile", json=payload)
        if resp.status_code == 200:
            return True
        print(f"    !! 创建用户档案失败 [{resp.status_code}]: {resp.text[:200]}")
        return False
    except httpx.RequestError as exc:
        print(f"    !! 请求异常: {exc}")
        return False


def create_item(client: httpx.Client, user_id: str, item: dict) -> bool:
    """POST /api/inventory 创建一条库存记录。"""
    payload = {
        "user_id": user_id,
        "name": item["name"],
        "quantity": item["quantity"],
        "unit": item["unit"],
        "item_type": item.get("item_type", "ingredient"),
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
    """按顺序注入：先档案、后库存。"""
    uid = scenario["user_id"]
    print(f"\n{'=' * 60}")
    print(f"  用户: {uid}")
    print(f"  描述: {scenario['description']}")
    print(f"{'=' * 60}")

    # 1. 注入用户档案
    profile = scenario.get("profile")
    if profile:
        print(f"\n  [1/2] 注入用户健康档案...")
        ok = create_profile(client, uid, profile)
        if ok:
            print(f"    ✓ 档案已创建")
        else:
            print(f"    !! 档案注入失败，后续菜谱推荐可能缺少偏好上下文")

    # 2. 注入库存食材
    items = scenario.get("inventory", [])
    print(f"\n  [2/3] 注入库存食材 ({len(items)} 种)...")
    if not items:
        print("    (空库存，跳过)")
    else:
        ok = sum(1 for item in items if create_item(client, uid, item))
        print(f"    ✓ 注入完成: {ok}/{len(items)} 条")

    # 3. 注入常用厨具
    equipment = scenario.get("equipment", [])
    print(f"\n  [3/3] 注入常用厨具 ({len(equipment)} 件)...")
    if not equipment:
        print("    (无厨具，跳过)")
    else:
        ok = sum(1 for eq in equipment if create_item(client, uid, eq))
        print(f"    ✓ 注入完成: {ok}/{len(equipment)} 件")


def print_guide() -> None:
    """打印手动验证指引。"""
    uid = SCENARIO["user_id"]
    eq = SCENARIO["profile"]["preferences"]["equipment"]
    print(f"""
{'=' * 60}
  Happy Path 全链路验证指引
  用户: {uid}
  常用厨具: {', '.join(eq)}
{'=' * 60}

1. 查询用户档案（含常用厨具）
   curl {API_BASE}/profile?user_id={uid}
   预期: 200 + 完整档案（含 preferences.equipment 和健康数据）

2. 查询库存列表
   curl "{API_BASE}/inventory?user_id={uid}"
   预期: 200 + 约 20 条库存记录，数量充足

3. 完整菜谱推荐（走搜索记忆 → 厨具检查 → LLM 生成）
   curl -X POST {API_BASE}/agents/recipe/recommend \\
     -H "Content-Type: application/json" \\
     -d '{{"user_id":"{uid}","meal_type":"dinner","target_calories":600,"available_equipment":["炒锅","汤锅","电饭煲","蒸锅","平底锅","空气炸锅"],"dietary_preferences":["高蛋白","低油"]}}'
   预期: 200 + 菜谱，feasible=true，rationale 含用户档案上下文字段（如"单身男性"）

4. 仅库存菜谱推荐
   curl -X POST {API_BASE}/agents/recipe/recommend-from-inventory \\
     -H "Content-Type: application/json" \\
     -d '{{"user_id":"{uid}","meal_type":"lunch","target_calories":500,"available_equipment":["炒锅","汤锅","电饭煲"],"dietary_preferences":["快手","中式"]}}'
   预期: 200 + 菜谱，ingredients 全部来自库存清单

5. 厨具检查（模拟菜谱需要烤箱但用户没有的场景）
   curl -X POST {API_BASE}/agents/equipment/check \\
     -H "Content-Type: application/json" \\
     -d '{{"equipment_owned":["炒锅","汤锅","电饭煲","蒸锅","平底锅","空气炸锅","微波炉"],"required_equipment":["炒锅","烤箱","料理机"]}}'
   预期: 200 + feasible=false，missing_equipment=["烤箱","料理机"]

6. 确认制作 → 扣库存 → 写历史（需先执行步骤 3 或 4 获取 recipe JSON）
   curl -X POST {API_BASE}/meals/confirm \\
     -H "Content-Type: application/json" \\
     -d '{{"user_id":"{uid}","recipe":<上一步返回的完整 JSON>}}'
   预期: 201 + deducted 非空，meal_id 有效

7. 查看饮食历史
   curl "{API_BASE}/meals/history?user_id={uid}&days=7"
   预期: 200 + 包含已确认的餐食

8. 查看菜谱库
   curl "{API_BASE}/recipes?user_id={uid}"
   预期: 200 + 包含已确认的菜谱，times_made >= 1

清理数据
   ./.conda/python.exe scripts/reset_data.py --user-prefix test-happy
""")


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def main() -> int:
    print("Sebastian 种子数据注入 — Happy Path 全链路验证")
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

    with httpx.Client(timeout=15) as client:
        seed_scenario(client, SCENARIO)

    print_guide()
    return 0


if __name__ == "__main__":
    sys.exit(main())
