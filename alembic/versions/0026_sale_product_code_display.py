"""add sale product code display parameter

Revision ID: 0026_sale_product_code_display
Revises: 0025_sale_payment_fields
Create Date: 2026-08-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_sale_product_code_display"
down_revision = "0025_sale_payment_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO system_params (key, value, description) "
            "VALUES (:key, :value, :description) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {
            "key": "sale_product_code_display",
            "value": "internal",
            "description": "Código mostrado en las líneas de venta: 'internal' o 'barcode'",
        },
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM system_params WHERE key = 'sale_product_code_display'")
    )
