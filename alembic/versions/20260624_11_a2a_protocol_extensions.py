"""A2A 协议扩展 — 扩展 agent_tasks 和 conversations 表，新增 agent_cards 表

Revision ID: 20260624_11
Revises: 20260624_10
Create Date: 2026-06-24

变更:
1. agent_tasks: 添加 context_id, agent_name, a2a_status, artifacts 列
2. conversations: 添加 summary 列（对话历史摘要缓存）
3. agent_cards: 新建表（Agent Card 元数据持久化）
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260624_11"
down_revision: Union[str, None] = "20260624_10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. 扩展 agent_tasks 表 ──────────────────────────────────────

    op.add_column(
        "agent_tasks",
        sa.Column("context_id", sa.String(128), nullable=True, comment="A2A 会话上下文 ID"),
    )
    op.create_index(op.f("ix_agent_tasks_context_id"), "agent_tasks", ["context_id"])

    op.add_column(
        "agent_tasks",
        sa.Column("agent_name", sa.String(64), nullable=True, comment="处理该任务的 Agent 名称"),
    )
    op.create_index(op.f("ix_agent_tasks_agent_name"), "agent_tasks", ["agent_name"])

    op.add_column(
        "agent_tasks",
        sa.Column(
            "a2a_status",
            sa.String(20),
            nullable=True,
            comment="A2A 任务状态: submitted/working/completed/failed/canceled",
        ),
    )

    op.add_column(
        "agent_tasks",
        sa.Column("artifacts", sa.JSON(), nullable=True, comment="A2A 任务产出列表"),
    )

    # ── 2. 扩展 conversations 表 ────────────────────────────────────

    op.add_column(
        "conversations",
        sa.Column("summary", sa.Text(), nullable=True, comment="对话历史 LLM 摘要缓存"),
    )

    # ── 3. 新建 agent_cards 表 ──────────────────────────────────────

    op.create_table(
        "agent_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False, comment="Agent 名称"),
        sa.Column("display_name", sa.String(128), nullable=False, comment="Agent 展示名称"),
        sa.Column("description", sa.String(512), nullable=True, comment="Agent 描述"),
        sa.Column("card_json", sa.JSON(), nullable=False, comment="完整 Agent Card JSON"),
        sa.Column("version", sa.String(20), nullable=False, server_default="0.1.0", comment="Agent Card 版本"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="是否启用"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_name"),
    )
    op.create_index(op.f("ix_agent_cards_agent_name"), "agent_cards", ["agent_name"], unique=True)


def downgrade() -> None:
    # ── 3. 删除 agent_cards 表 ──────────────────────────────────────

    op.drop_index(op.f("ix_agent_cards_agent_name"), table_name="agent_cards")
    op.drop_table("agent_cards")

    # ── 2. 回退 conversations 变更 ──────────────────────────────────

    op.drop_column("conversations", "summary")

    # ── 1. 回退 agent_tasks 变更 ────────────────────────────────────

    op.drop_column("agent_tasks", "artifacts")
    op.drop_column("agent_tasks", "a2a_status")
    op.drop_index(op.f("ix_agent_tasks_agent_name"), table_name="agent_tasks")
    op.drop_column("agent_tasks", "agent_name")
    op.drop_index(op.f("ix_agent_tasks_context_id"), table_name="agent_tasks")
    op.drop_column("agent_tasks", "context_id")
