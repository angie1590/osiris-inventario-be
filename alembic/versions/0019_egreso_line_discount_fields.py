"""add egreso line discount fields

Revision ID: 0019_egreso_line_discount_fields
Revises: 0018_baja_reason_and_config
Create Date: 2026-07-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_egreso_line_discount_fields"
down_revision = "0018_baja_reason_and_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_document_lines",
        sa.Column("unit_price_base", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "inventory_document_lines",
        sa.Column("discount_type", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "inventory_document_lines",
        sa.Column("discount_value", sa.Numeric(14, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_document_lines", "discount_value")
    op.drop_column("inventory_document_lines", "discount_type")
    op.drop_column("inventory_document_lines", "unit_price_base")
