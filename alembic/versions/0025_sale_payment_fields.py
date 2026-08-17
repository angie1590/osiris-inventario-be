"""add sale payment fields and company payment catalogs

Revision ID: 0025_sale_payment_fields
Revises: 0024_exchange_product_change
Create Date: 2026-08-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0025_sale_payment_fields"
down_revision = "0024_exchange_product_change"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_config",
        sa.Column(
            "payment_methods",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[{\"name\": \"EFECTIVO\", \"active\": true, \"default\": true, \"requires_bank\": false}, {\"name\": \"TRANSFERENCIA\", \"active\": true, \"default\": false, \"requires_bank\": true}]'::jsonb"),
        ),
    )
    op.add_column(
        "company_config",
        sa.Column(
            "banks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("inventory_documents", sa.Column("payment_method", sa.String(length=50), nullable=True))
    op.add_column("inventory_documents", sa.Column("bank_name", sa.String(length=150), nullable=True))
    op.add_column("inventory_documents", sa.Column("amount_received", sa.Numeric(14, 2), nullable=True))
    op.add_column("inventory_documents", sa.Column("change_amount", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_documents", "change_amount")
    op.drop_column("inventory_documents", "amount_received")
    op.drop_column("inventory_documents", "bank_name")
    op.drop_column("inventory_documents", "payment_method")
    op.drop_column("company_config", "banks")
    op.drop_column("company_config", "payment_methods")