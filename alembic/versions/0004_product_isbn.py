"""Add isbn to products

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("isbn", sa.String(length=32), nullable=True))
    op.execute("""
        UPDATE products
        SET isbn = 'ISBN-' || LPAD(id::text, 10, '0')
        WHERE isbn IS NULL OR isbn = ''
        """)
    op.alter_column(
        "products", "isbn", existing_type=sa.String(length=32), nullable=False
    )
    op.create_index("ix_products_isbn", "products", ["isbn"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_products_isbn", table_name="products")
    op.drop_column("products", "isbn")
