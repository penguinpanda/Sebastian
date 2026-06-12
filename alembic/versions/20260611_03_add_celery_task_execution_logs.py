"""add celery task execution logs table

Revision ID: 20260611_03
Revises: 20260609_02
Create Date: 2026-06-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260611_03"
down_revision: str | None = "20260609_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "celery_task_execution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("task_name", sa.String(length=120), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_celery_task_execution_logs_task_id"),
    )
    op.create_index("ix_celery_task_execution_logs_task_id", "celery_task_execution_logs", ["task_id"])
    op.create_index("ix_celery_task_execution_logs_trace_id", "celery_task_execution_logs", ["trace_id"])
    op.create_index("ix_celery_task_execution_logs_status", "celery_task_execution_logs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_celery_task_execution_logs_status", table_name="celery_task_execution_logs")
    op.drop_index("ix_celery_task_execution_logs_trace_id", table_name="celery_task_execution_logs")
    op.drop_index("ix_celery_task_execution_logs_task_id", table_name="celery_task_execution_logs")
    op.drop_table("celery_task_execution_logs")