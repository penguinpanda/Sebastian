"""add recipes table

Revision ID: 20260612_06
Revises: 20260612_05
Create Date: 2026-06-12

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260612_06"
down_revision: str | None = "20260612_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("estimated_calories", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingredients", sa.JSON(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=True),
        sa.Column("required_equipment", sa.JSON(), nullable=True),
        sa.Column("recipe_data", sa.JSON(), nullable=True),
        sa.Column("times_made", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_hash", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipes_user_id", "recipes", ["user_id"])
    op.create_index("ix_recipes_content_hash", "recipes", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_recipes_content_hash", table_name="recipes")
    op.drop_index("ix_recipes_user_id", table_name="recipes")
    op.drop_table("recipes")
