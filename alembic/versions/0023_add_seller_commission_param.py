"""add seller commission percent system param

Revision ID: 0023_seller_commission_param
Revises: 0022_company_sellers_egreso
Create Date: 2026-07-23 00:00:00.000000
"""

from alembic import op


revision = "0023_seller_commission_param"
down_revision = "0022_company_sellers_egreso"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO system_params (key, value, description)
        SELECT 'seller_commission_percent', '0', 'Porcentaje de comision para vendedores (0-100)'
        WHERE NOT EXISTS (
            SELECT 1 FROM system_params WHERE key = 'seller_commission_percent'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM system_params
        WHERE key = 'seller_commission_percent'
          AND value = '0'
        """
    )
