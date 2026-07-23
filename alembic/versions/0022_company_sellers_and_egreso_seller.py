"""add company sellers and egreso seller

Revision ID: 0022_company_sellers_egreso
Revises: 0021_inventory_counts
Create Date: 2026-07-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0022_company_sellers_egreso"
down_revision = "0021_inventory_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_config",
        sa.Column(
            "sellers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("seller_name", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_documents", "seller_name")
    op.drop_column("company_config", "sellers")
