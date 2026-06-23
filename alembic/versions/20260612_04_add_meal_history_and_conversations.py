"""add meal_history and conversations tables

Revision ID: 20260612_04
Revises: 20260611_03
Create Date: 2026-06-12

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260612_04"
down_revision: str | None = "20260611_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meal_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("meal_date", sa.Date(), nullable=False),
        sa.Column("recipe_title", sa.String(length=200), nullable=False),
        sa.Column("estimated_calories", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recipe_data", sa.JSON(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meal_history_user_id", "meal_history", ["user_id"])
    op.create_index("ix_meal_history_meal_date", "meal_history", ["meal_date"])

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_date", sa.Date(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_date", "conversations", ["conversation_date"])


def downgrade() -> None:
    op.drop_index("ix_conversations_date", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_meal_history_meal_date", table_name="meal_history")
    op.drop_index("ix_meal_history_user_id", table_name="meal_history")
    op.drop_table("meal_history")
