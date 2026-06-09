"""master catalogs + 'catalog' attribute type

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New attribute data type for catalog-backed attributes.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE attributedatatype ADD VALUE IF NOT EXISTS 'catalog'")

    op.create_table(
        "catalogs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "catalog_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_id", sa.Integer(), sa.ForeignKey("catalogs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("value", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column(
        "category_attributes",
        sa.Column("catalog_id", sa.Integer(), sa.ForeignKey("catalogs.id", ondelete="RESTRICT"), nullable=True),
    )
    op.create_index("ix_category_attributes_catalog_id", "category_attributes", ["catalog_id"])


def downgrade() -> None:
    op.drop_index("ix_category_attributes_catalog_id", table_name="category_attributes")
    op.drop_column("category_attributes", "catalog_id")
    op.drop_table("catalog_values")
    op.drop_table("catalogs")
