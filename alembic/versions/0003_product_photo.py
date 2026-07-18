"""add product photo

Revision ID: 0003_product_photo
Revises: 0012_rename_isbn_required_param
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_product_photo"
down_revision = "0012_rename_isbn_required_param"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("photo", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "photo")
