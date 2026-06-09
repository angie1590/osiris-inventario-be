"""attribute allow_negative + isbn_required param + internal_code default on

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "category_attributes",
        sa.Column("allow_negative", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Internal product code is enabled by default (companies opt out in params).
    op.execute("UPDATE system_params SET value = 'true' WHERE key = 'internal_code_enabled'")
    # New param: whether ISBN is mandatory on products.
    op.execute(
        """
        INSERT INTO system_params (key, value, description)
        VALUES ('isbn_required', 'false', 'Hace obligatorio el ISBN al crear/editar productos')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_params WHERE key = 'isbn_required'")
    op.drop_column("category_attributes", "allow_negative")
