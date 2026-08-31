"""add sale outstanding amount

Revision ID: 0028_sale_outstanding_amount
Revises: 0027_inventory_customers
Create Date: 2026-08-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0028_sale_outstanding_amount"
down_revision = "0027_inventory_customers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_documents",
        sa.Column("outstanding_amount", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_documents", "outstanding_amount")