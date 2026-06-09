"""add codigo_interno to products + internal_code_enabled param

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("codigo_interno", sa.String(length=50), nullable=True))
    op.create_index("ix_products_codigo_interno", "products", ["codigo_interno"])
    op.execute(
        """
        INSERT INTO system_params (key, value, description)
        VALUES ('internal_code_enabled', 'false',
                'Habilita el código interno alfanumérico de productos (búsqueda y formulario)')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_params WHERE key = 'internal_code_enabled'")
    op.drop_index("ix_products_codigo_interno", table_name="products")
    op.drop_column("products", "codigo_interno")
