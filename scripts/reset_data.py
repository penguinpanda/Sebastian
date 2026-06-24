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
    7. Agent 任务记录（agent_tasks）
    8. 工具调用日志（tool_call_logs）
    9. Celery 执行日志（celery_task_execution_logs）
   10. Elasticsearch 用户记忆（memory_index）
   11. Redis 缓存（agent 队列 / 频率限制 / 幂等缓存）
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
    "test-happy-001",
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

def clear_inventory(client: httpx.Client, user_ids: list[str] | None = None) -> dict:
    """列出并逐条删除库存项。

    若提供 user_ids，则逐个用户清除；否则仅清除默认用户的库存。
    """
    result = {"deleted": 0, "failed": 0, "errors": []}

    targets = user_ids if user_ids else ["default"]

    for uid in targets:
        try:
            resp = client.get(f"{API_BASE}/inventory", params={"user_id": uid})
            if resp.status_code != 200:
                result["errors"].append(f"[{uid}] 列出库存失败 [{resp.status_code}]: {resp.text[:200]}")
                continue

            items = resp.json()
            if not items:
                print(f"  - [{uid}] 无库存数据")
                continue

            for item in items:
                item_id = item.get("id")
                name = item.get("name", "?")
                try:
                    del_resp = client.delete(f"{API_BASE}/inventory/{item_id}")
                    if del_resp.status_code == 204:
                        result["deleted"] += 1
                        print(f"  ✓ [{uid}] 已删除: {name} ({item_id[:8]}...)")
                    else:
                        result["failed"] += 1
                        result["errors"].append(f"[{uid}] 删除 {name} 失败 [{del_resp.status_code}]")
                except httpx.RequestError as exc:
                    result["failed"] += 1
                    result["errors"].append(f"[{uid}] 删除 {name} 异常: {exc}")

        except httpx.RequestError as exc:
            result["errors"].append(f"[{uid}] 列出库存异常: {exc}")

    return result


# ═══════════════════════════════════════════════════════════
# 步骤 2：数据库级清理（直接操作 PostgreSQL）
# ═══════════════════════════════════════════════════════════

def clear_via_database(user_prefix: str | None = None) -> dict:
    """通过 SQLAlchemy 直接删除数据（无需 API）。"""
    result = {"cleared_tables": [], "errors": []}

    try:
        from app.db.session import get_db_session
        from app.models.agent import AgentTask, ToolCallLog
        from app.models.conversation import Conversation
        from app.models.inventory import Inventory, InventoryTransaction
        from app.models.meal import MealHistory
        from app.models.recipe import Recipe
        from app.models.task_execution import CeleryTaskExecutionLog
        from app.models.user_profile import UserProfile

        db = next(get_db_session())

        # (表名, 模型, 是否有 user_id 列)
        tables_to_clear: list[tuple[str, type, bool]] = [
            ("tool_call_logs", ToolCallLog, False),
            ("inventory_transactions", InventoryTransaction, True),
            ("meal_history", MealHistory, True),
            ("recipes", Recipe, True),
            ("conversations", Conversation, True),
            ("agent_tasks", AgentTask, True),
            ("celery_task_execution_logs", CeleryTaskExecutionLog, False),
            ("user_profiles", UserProfile, True),
            ("inventories", Inventory, True),
        ]

        for table_name, model, has_user_id in tables_to_clear:
            try:
                if user_prefix and has_user_id:
                    stmt = model.__table__.delete().where(
                        model.user_id.like(f"{user_prefix}%")
                    )
                elif user_prefix and not has_user_id:
                    # 无 user_id 列的表（如 celery_task_execution_logs）在指定前缀时
                    # 无法按用户过滤，全量清理这些日志表
                    stmt = model.__table__.delete()
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
        print(f"  !! 导入失败: {exc}")
        print(f"  !! 请确认使用 conda 环境运行: ./.conda/python.exe scripts/reset_data.py --db-only -y")
    except Exception as exc:
        result["errors"].append(f"数据库清理异常: {exc}")
        print(f"  !! 数据库清理异常: {exc}")

    return result


# ═══════════════════════════════════════════════════════════
# 步骤 3：清除 Elasticsearch 记忆
# ═══════════════════════════════════════════════════════════

def clear_elasticsearch_memories(user_prefix: str | None = None) -> dict:
    """删除 Elasticsearch 中存储的用户记忆。

    若提供 user_prefix，只删除匹配前缀的用户记忆；
    否则删除整个 memory_index 索引（重建由 SearchService.ensure_memory_index 自动完成）。
    """
    result: dict = {"deleted": 0, "message": "", "errors": []}

    try:
        from app.core.config import get_settings
        from app.integrations.elasticsearch_client import get_elasticsearch_client

        settings = get_settings()
        client = get_elasticsearch_client()
        index = settings.elasticsearch_memory_index

        if not client.indices.exists(index=index):
            result["message"] = "ES 索引不存在，跳过"
            print(f"  - ES 索引 '{index}' 不存在，跳过")
            return result

        if user_prefix:
            resp = client.delete_by_query(
                index=index,
                body={"query": {"prefix": {"user_id": user_prefix}}},
                refresh=True,
                conflicts="proceed",
            )
            deleted = int(resp.get("deleted", 0))
            result["deleted"] = deleted
            result["message"] = f"已删除 {deleted} 条匹配前缀 '{user_prefix}' 的记忆"
            print(f"  ✓ ES: {result['message']}")
        else:
            client.indices.delete(index=index)
            result["deleted"] = -1
            result["message"] = f"已删除整个索引 '{index}'（下次写入时自动重建）"
            print(f"  ✓ ES: {result['message']}")

    except ImportError:
        msg = "Elasticsearch 模块未安装，跳过（请确认使用 conda 环境）"
        result["errors"].append(msg)
        print(f"  - ES: {msg}")
    except Exception as exc:
        result["errors"].append(str(exc))
        print(f"  !! ES 清理失败: {exc}")

    return result


# ═══════════════════════════════════════════════════════════
# 步骤 4：清除 Redis 缓存
# ═══════════════════════════════════════════════════════════

def clear_redis_cache() -> dict:
    """清空 Redis 中所有缓存数据（agent 任务队列、频率限制、幂等缓存等）。"""
    result: dict = {"keys_deleted": 0, "errors": []}

    try:
        from app.integrations.redis_client import get_redis_client

        client = get_redis_client()
        client.flushdb()
        result["keys_deleted"] = -1
        print("  ✓ Redis: 已清空当前数据库所有键")

    except ImportError:
        msg = "Redis 模块未安装，跳过（请确认使用 conda 环境）"
        result["errors"].append(msg)
        print(f"  - Redis: {msg}")
    except Exception as exc:
        result["errors"].append(str(exc))
        print(f"  !! Redis 清理失败: {exc}")

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

    # 确定 API 模式下要清理的用户列表
    if user_prefix:
        api_user_ids = [uid for uid in SEED_USER_IDS if uid.startswith(user_prefix)]
        print(f"清理范围: user_id 前缀 = '{user_prefix}'")
        if api_user_ids:
            print(f"  匹配的种子用户: {', '.join(api_user_ids)}")
    else:
        api_user_ids = None  # None = 仅清默认用户（全量清理走 DB 模式）
        print("⚠️  清理范围: 全部数据（所有用户）")
        if not args.db_only and not args.api_only:
            print("  提示: 全量清理推荐使用 --db-only 模式，可直接清空所有表。")

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
                inv_result = clear_inventory(client, user_ids=api_user_ids)
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

    # ── Elasticsearch 记忆清理 ──
    if not args.api_only:
        print("\n── 3. Elasticsearch 记忆清理 ──")
        es_result = clear_elasticsearch_memories(user_prefix=user_prefix)
        if es_result["errors"]:
            success = False

    # ── Redis 缓存清理 ──
    if not args.api_only:
        print("\n── 4. Redis 缓存清理 ──")
        redis_result = clear_redis_cache()
        if redis_result["errors"]:
            success = False

    # ── 结果 ──
    print()
    if success:
        print("✅ 重置完成。所有数据（数据库 + ES 记忆 + Redis 缓存）已清空。")
        if not args.db_only:
            print(f"   可重新注入种子数据：./.conda/python.exe scripts/seed_inventory_test_data.py")
            print(f"   或注入 Happy Path 数据：./.conda/python.exe scripts/seed_happy_path_data.py")
    else:
        print("⚠️  重置完成（部分操作有误）。")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
