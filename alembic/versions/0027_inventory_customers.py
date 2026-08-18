"""add inventory customers catalog

Revision ID: 0027_inventory_customers
Revises: 0026_sale_product_code_display
Create Date: 2026-08-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_inventory_customers"
down_revision = "0026_sale_product_code_display"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "identification_type",
            sa.String(length=20),
            nullable=False,
            server_default="cedula",
        ),
        sa.Column("identification_number", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "identification_type",
            "identification_number",
            name="uq_inventory_customer_identification",
        ),
    )
    op.create_index(
        "ix_inventory_customers_identification_type",
        "inventory_customers",
        ["identification_type"],
    )
    op.create_index(
        "ix_inventory_customers_is_active", "inventory_customers", ["is_active"]
    )

    op.add_column(
        "inventory_documents",
        sa.Column("customer_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_inventory_documents_customer_id", "inventory_documents", ["customer_id"]
    )
    op.create_foreign_key(
        "fk_inventory_documents_customer_id",
        "inventory_documents",
        "inventory_customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inventory_documents_customer_id", "inventory_documents", type_="foreignkey"
    )
    op.drop_index("ix_inventory_documents_customer_id", "inventory_documents")
    op.drop_column("inventory_documents", "customer_id")
    op.drop_index("ix_inventory_customers_is_active", "inventory_customers")
    op.drop_index(
        "ix_inventory_customers_identification_type", "inventory_customers"
    )
    op.drop_table("inventory_customers")
