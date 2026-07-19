"""add ingreso purchase metadata, suppliers and attachments

Revision ID: 0014_ingreso_purchase_fields
Revises: 0013_product_photos_gallery
Create Date: 2026-07-18 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0014_ingreso_purchase_fields"
down_revision = "0013_product_photos_gallery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ruc", sa.String(length=13), nullable=False),
        sa.Column("trade_name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_inventory_suppliers_ruc", "inventory_suppliers", ["ruc"], unique=True)
    op.create_index("ix_inventory_suppliers_is_active", "inventory_suppliers", ["is_active"])

    op.add_column("inventory_documents", sa.Column("ingreso_type", sa.String(length=30), nullable=True))
    op.add_column("inventory_documents", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.add_column(
        "inventory_documents",
        sa.Column("purchase_document_type", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("purchase_document_number", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("purchase_document_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_inventory_documents_supplier_id", "inventory_documents", ["supplier_id"])
    op.create_foreign_key(
        "fk_inventory_documents_supplier_id",
        "inventory_documents",
        "inventory_suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "inventory_document_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["inventory_documents.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_inventory_document_attachments_document_id",
        "inventory_document_attachments",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_document_attachments_document_id",
        table_name="inventory_document_attachments",
    )
    op.drop_table("inventory_document_attachments")

    op.drop_constraint(
        "fk_inventory_documents_supplier_id",
        "inventory_documents",
        type_="foreignkey",
    )
    op.drop_index("ix_inventory_documents_supplier_id", table_name="inventory_documents")
    op.drop_column("inventory_documents", "purchase_document_date")
    op.drop_column("inventory_documents", "purchase_document_number")
    op.drop_column("inventory_documents", "purchase_document_type")
    op.drop_column("inventory_documents", "supplier_id")
    op.drop_column("inventory_documents", "ingreso_type")

    op.drop_index("ix_inventory_suppliers_is_active", table_name="inventory_suppliers")
    op.drop_index("ix_inventory_suppliers_ruc", table_name="inventory_suppliers")
    op.drop_table("inventory_suppliers")
