"""pending attribute remap (type-change migration)

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_attribute_remap",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("attribute_id", sa.Integer(), sa.ForeignKey("category_attributes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("attribute_name", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pending_attribute_remap")
