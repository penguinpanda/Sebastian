"""add item_type to inventories

Revision ID: 20260624_10
Revises: 20260623_09
Create Date: 2026-06-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260624_10"
down_revision: Union[str, None] = "20260623_09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inventories",
        sa.Column("item_type", sa.String(20), nullable=False, server_default="ingredient"),
    )
    op.create_index(op.f("ix_inventories_item_type"), "inventories", ["item_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_inventories_item_type"), table_name="inventories")
    op.drop_column("inventories", "item_type")
