"""Add is_active to category_attributes

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "category_attributes",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_category_attributes_is_active", "category_attributes", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_category_attributes_is_active", table_name="category_attributes")
    op.drop_column("category_attributes", "is_active")
