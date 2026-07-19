"""add product photos gallery

Revision ID: 0013_product_photos_gallery
Revises: 0003_product_photo
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_product_photos_gallery"
down_revision = "0003_product_photo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("photos", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute(
        """
        UPDATE products
        SET photos = CASE
            WHEN photo IS NOT NULL AND btrim(photo) <> ''
            THEN jsonb_build_array(jsonb_build_object('url', photo, 'is_cover', true))
            ELSE NULL
        END
        """
    )


def downgrade() -> None:
    op.drop_column("products", "photos")
