"""add agent_tasks and tool_call_logs tables

Revision ID: 20260609_02
Revises: 20260609_01
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260609_02"
down_revision: str | None = "20260609_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tasks_user_id", "agent_tasks", ["user_id"])

    op.create_table(
        "tool_call_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("result_status", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_call_logs_task_id", "tool_call_logs", ["task_id"])
    op.create_index("ix_tool_call_logs_trace_id", "tool_call_logs", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_call_logs_trace_id", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_task_id", table_name="tool_call_logs")
    op.drop_table("tool_call_logs")
    op.drop_index("ix_agent_tasks_user_id", table_name="agent_tasks")
    op.drop_table("agent_tasks")
