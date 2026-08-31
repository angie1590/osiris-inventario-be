"""add sale credit applied amount

Revision ID: 0029_sale_credit_applied_amount
Revises: 0028_sale_outstanding_amount
Create Date: 2026-08-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0029_sale_credit_applied_amount"
down_revision = "0028_sale_outstanding_amount"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_documents",
        sa.Column("credit_applied_amount", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_documents", "credit_applied_amount")