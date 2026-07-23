"""add inventory counts

Revision ID: 0021_inventory_counts
Revises: 0020_egreso_adjustment_reason
Create Date: 2026-07-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_inventory_counts"
down_revision = "0020_egreso_adjustment_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "count_sequences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prefix", sa.String(length=10), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefix", "year", name="uq_count_sequence"),
    )
    op.create_table(
        "inventory_counts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("positive_adjustment_document_id", sa.Integer(), nullable=True),
        sa.Column("negative_adjustment_document_id", sa.Integer(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["negative_adjustment_document_id"],
            ["inventory_documents.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["positive_adjustment_document_id"],
            ["inventory_documents.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index(op.f("ix_inventory_counts_number"), "inventory_counts", ["number"], unique=False)
    op.create_index(op.f("ix_inventory_counts_status"), "inventory_counts", ["status"], unique=False)
    op.create_index(op.f("ix_inventory_counts_created_by"), "inventory_counts", ["created_by"], unique=False)
    op.create_table(
        "inventory_count_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("count_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("product_isbn_snapshot", sa.String(length=50), nullable=True),
        sa.Column("product_codigo_interno_snapshot", sa.String(length=100), nullable=True),
        sa.Column("system_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("physical_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("difference_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["count_id"], ["inventory_counts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_count_lines_count_id"), "inventory_count_lines", ["count_id"], unique=False)
    op.create_index(op.f("ix_inventory_count_lines_product_id"), "inventory_count_lines", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_inventory_count_lines_product_id"), table_name="inventory_count_lines")
    op.drop_index(op.f("ix_inventory_count_lines_count_id"), table_name="inventory_count_lines")
    op.drop_table("inventory_count_lines")
    op.drop_index(op.f("ix_inventory_counts_created_by"), table_name="inventory_counts")
    op.drop_index(op.f("ix_inventory_counts_status"), table_name="inventory_counts")
    op.drop_index(op.f("ix_inventory_counts_number"), table_name="inventory_counts")
    op.drop_table("inventory_counts")
    op.drop_table("count_sequences")