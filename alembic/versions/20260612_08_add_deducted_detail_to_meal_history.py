"""add deducted_detail and rolled_back_at to meal_history

Revision ID: 20260612_08
Revises: 20260612_07
Create Date: 2026-06-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260612_08"
down_revision: Union[str, None] = "20260612_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("meal_history", sa.Column("deducted_detail", sa.JSON(), nullable=True))
    op.add_column("meal_history", sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("meal_history", "rolled_back_at")
    op.drop_column("meal_history", "deducted_detail")
