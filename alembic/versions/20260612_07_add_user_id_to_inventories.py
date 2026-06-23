"""add user_id to inventories

Revision ID: 20260612_07
Revises: 20260612_06
Create Date: 2026-06-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260612_07"
down_revision: Union[str, None] = "20260612_06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inventories",
        sa.Column("user_id", sa.String(64), nullable=False, server_default="default"),
    )
    op.create_index(op.f("ix_inventories_user_id"), "inventories", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_inventories_user_id"), table_name="inventories")
    op.drop_column("inventories", "user_id")
