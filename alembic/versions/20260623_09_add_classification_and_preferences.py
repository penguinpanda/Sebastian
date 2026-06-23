"""add classification and preferences to user_profiles

Revision ID: 20260623_09
Revises: 20260612_08
Create Date: 2026-06-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260623_09"
down_revision: Union[str, None] = "20260612_08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("classification", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column("preferences", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "preferences")
    op.drop_column("user_profiles", "classification")
