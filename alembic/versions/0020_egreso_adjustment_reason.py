"""add egreso adjustment reason

Revision ID: 0020_egreso_adjustment_reason
Revises: 0019_egreso_line_discount_fields
Create Date: 2026-07-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_egreso_adjustment_reason"
down_revision = "0019_egreso_line_discount_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_documents",
        sa.Column("adjustment_reason", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_documents", "adjustment_reason")
