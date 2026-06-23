# -*- coding: utf-8 -*-
"""重置脚本 — 快速将 Sebastian 项目恢复到空白状态。

用法（需先启动后端 API）：
    ./.conda/python.exe scripts/reset_data.py

或指定 user_id 范围清理：
    ./.conda/python.exe scripts/reset_data.py --user-prefix test-inv-only

覆盖清理范围：
    1. 库存数据（inventories）
    2. 库存交易记录（inventory_transactions）
    3. 饮食历史（meal_history）
    4. 菜谱库（recipes）
    5. 对话记录（conversations）
    6. 用户健康档案（user_profiles）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

API_BASE = "http://127.0.0.1:8000/api"

# ═══════════════════════════════════════════════════════════
# 种子测试用的 user_id 前缀（与 seed_inventory_test_data.py 保持一致）
# ═══════════════════════════════════════════════════════════

SEED_USER_IDS = [
    "test-inv-only-001",
    "test-inv-only-002",
    "test-inv-only-003",
    "test-inv-only-004",
    "test-inv-only-005",
]


def check_api_health(client: httpx.Client) -> bool:
    """验证 API 可达。"""
    try:
        resp = client.get(f"{API_BASE}/health")
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


# ═══════════════════════════════════════════════════════════
# 步骤 1：清除库存
# ═══════════════════════════════════════════════════════════

def clear_inventory(client: httpx.Client) -> dict:
    """列出并逐条删除所有库存项。"""
    result = {"deleted": 0, "failed": 0, "errors": []}

    try:
        resp = client.get(f"{API_BASE}/inventory")
        if resp.status_code != 200:
            result["errors"].append(f"列出库存失败 [{resp.status_code}]: {resp.text[:200]}")
            return result

        items = resp.json()
        for item in items:
            item_id = item.get("id")
            name = item.get("name", "?")
            try:
                del_resp = client.delete(f"{API_BASE}/inventory/{item_id}")
                if del_resp.status_code == 204:
                    result["deleted"] += 1
                    print(f"  ✓ 已删除: {name} ({item_id[:8]}...)")
                else:
                    result["failed"] += 1
                    result["errors"].append(f"删除 {name} 失败 [{del_resp.status_code}]")
            except httpx.RequestError as exc:
                result["failed"] += 1
                result["errors"].append(f"删除 {name} 异常: {exc}")

    except httpx.RequestError as exc:
        result["errors"].append(f"列出库存异常: {exc}")

    return result


# ═══════════════════════════════════════════════════════════
# 步骤 2：数据库级清理（直接操作 PostgreSQL）
# ═══════════════════════════════════════════════════════════

def clear_via_database(user_prefix: str | None = None) -> dict:
    """通过 SQLAlchemy 直接删除数据（无需 API）。"""
    result = {"cleared_tables": [], "errors": []}

    try:
        from app.db.session import get_db_session
        from app.models.inventory import Inventory, InventoryTransaction
        from app.models.meal import MealHistory
        from app.models.recipe import Recipe
        from app.models.conversation import Conversation
        from app.models.user_profile import UserProfile

        db = next(get_db_session())

        tables_to_clear: list[tuple[str, type]] = [
            ("inventory_transactions", InventoryTransaction),
            ("meal_history", MealHistory),
            ("recipes", Recipe),
            ("conversations", Conversation),
            ("user_profiles", UserProfile),
            ("inventories", Inventory),
        ]

        for table_name, model in tables_to_clear:
            try:
                if user_prefix:
                    # 只清理匹配前缀的 user_id
                    stmt = model.__table__.delete().where(
                        model.user_id.like(f"{user_prefix}%")
                    )
                else:
                    stmt = model.__table__.delete()
                result_proxy = db.execute(stmt)
                rowcount = result_proxy.rowcount
                db.commit()
                if rowcount > 0:
                    result["cleared_tables"].append(f"{table_name} ({rowcount} 条)")
                    print(f"  ✓ 已清理: {table_name} ({rowcount} 条)")
                else:
                    print(f"  - 无数据: {table_name}")
            except Exception as exc:
                db.rollback()
                result["errors"].append(f"{table_name}: {exc}")
                print(f"  !! {table_name} 清理失败: {exc}")

        db.close()
    except ImportError as exc:
        result["errors"].append(f"无法导入 SQLAlchemy 模块: {exc}")
    except Exception as exc:
        result["errors"].append(f"数据库清理异常: {exc}")

    return result


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="重置 Sebastian 项目数据到空白状态"
    )
    parser.add_argument(
        "--user-prefix",
        type=str,
        default=None,
        help="仅清理匹配此前缀的 user_id（例如 test-inv-only）",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="仅通过 API 清理库存（不操作数据库）",
    )
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="仅通过数据库清理（不调用 API）",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="跳过确认提示",
    )
    args = parser.parse_args()

    user_prefix = args.user_prefix

    if user_prefix:
        print(f"清理范围: user_id 前缀 = '{user_prefix}'")
    else:
        print("⚠️  清理范围: 全部数据（所有用户）")

    if not args.yes:
        confirm = input("\n确认重置数据？[y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("已取消。")
            return 0

    print()
    success = True

    # ── API 模式：通过 REST 删除库存 ──
    if not args.db_only:
        print("── 1. API 层清理库存 ──")
        with httpx.Client(timeout=5) as client:
            if not check_api_health(client):
                print("  ⚠️  API 不可达，跳过 API 清理。请先启动后端或使用 --db-only 模式。")
            else:
                inv_result = clear_inventory(client)
                if inv_result["errors"]:
                    success = False
                print(f"  总结: 删除 {inv_result['deleted']} 条，失败 {inv_result['failed']} 条")

    # ── 数据库模式：直接清表 ──
    if not args.api_only:
        print("\n── 2. 数据库层清理 ──")
        db_result = clear_via_database(user_prefix=user_prefix)
        if db_result["errors"]:
            success = False
        if db_result["cleared_tables"]:
            print(f"  总结: 已清理 {len(db_result['cleared_tables'])} 个表")

    # ── 结果 ──
    print()
    if success:
        print("✅ 重置完成。")
        print(f"   可重新注入种子数据：./.conda/python.exe scripts/seed_inventory_test_data.py")
    else:
        print("⚠️  重置完成（部分操作有误）。")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
