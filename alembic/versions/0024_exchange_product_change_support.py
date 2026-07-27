"""add exchange relation fields and return condition metadata

Revision ID: 0024_exchange_product_change
Revises: 0023_seller_commission_param
Create Date: 2026-07-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_exchange_product_change"
down_revision = "0023_seller_commission_param"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_documents",
        sa.Column("exchange_original_document_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("exchange_original_document_number", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("exchange_return_document_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("exchange_return_document_number", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("exchange_new_sale_document_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("exchange_new_sale_document_number", sa.String(length=20), nullable=True),
    )

    op.create_index(
        "ix_inventory_documents_exchange_original_document_id",
        "inventory_documents",
        ["exchange_original_document_id"],
    )
    op.create_index(
        "ix_inventory_documents_exchange_return_document_id",
        "inventory_documents",
        ["exchange_return_document_id"],
    )
    op.create_index(
        "ix_inventory_documents_exchange_new_sale_document_id",
        "inventory_documents",
        ["exchange_new_sale_document_id"],
    )

    op.add_column(
        "inventory_document_lines",
        sa.Column("return_condition", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "inventory_document_lines",
        sa.Column("return_reason", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "inventory_document_lines",
        sa.Column("return_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_document_lines", "return_notes")
    op.drop_column("inventory_document_lines", "return_reason")
    op.drop_column("inventory_document_lines", "return_condition")

    op.drop_index(
        "ix_inventory_documents_exchange_new_sale_document_id",
        table_name="inventory_documents",
    )
    op.drop_index(
        "ix_inventory_documents_exchange_return_document_id",
        table_name="inventory_documents",
    )
    op.drop_index(
        "ix_inventory_documents_exchange_original_document_id",
        table_name="inventory_documents",
    )

    op.drop_column("inventory_documents", "exchange_new_sale_document_number")
    op.drop_column("inventory_documents", "exchange_new_sale_document_id")
    op.drop_column("inventory_documents", "exchange_return_document_number")
    op.drop_column("inventory_documents", "exchange_return_document_id")
    op.drop_column("inventory_documents", "exchange_original_document_number")
    op.drop_column("inventory_documents", "exchange_original_document_id")
