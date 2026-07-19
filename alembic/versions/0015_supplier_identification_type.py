"""add supplier identification type

Revision ID: 0015_supplier_ident_type
Revises: 0014_ingreso_purchase_fields
Create Date: 2026-07-18 20:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0015_supplier_ident_type"
down_revision = "0014_ingreso_purchase_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.add_column(
		"inventory_suppliers",
		sa.Column(
			"identification_type",
			sa.String(length=20),
			nullable=True,
			server_default="ruc",
		),
	)
	op.execute(
		"UPDATE inventory_suppliers SET identification_type = 'ruc' WHERE identification_type IS NULL"
	)
	op.alter_column(
		"inventory_suppliers",
		"identification_type",
		existing_type=sa.String(length=20),
		nullable=False,
		server_default=None,
	)
	op.alter_column(
		"inventory_suppliers",
		"ruc",
		existing_type=sa.String(length=13),
		type_=sa.String(length=20),
		existing_nullable=False,
	)
	op.drop_index("ix_inventory_suppliers_ruc", table_name="inventory_suppliers")
	op.create_unique_constraint(
		"uq_inventory_supplier_identification",
		"inventory_suppliers",
		["identification_type", "ruc"],
	)
	op.create_index(
		"ix_inventory_suppliers_identification_type",
		"inventory_suppliers",
		["identification_type"],
		unique=False,
	)


def downgrade() -> None:
	op.drop_index(
		"ix_inventory_suppliers_identification_type",
		table_name="inventory_suppliers",
	)
	op.drop_constraint(
		"uq_inventory_supplier_identification",
		"inventory_suppliers",
		type_="unique",
	)
	op.create_index("ix_inventory_suppliers_ruc", "inventory_suppliers", ["ruc"], unique=True)
	op.alter_column(
		"inventory_suppliers",
		"ruc",
		existing_type=sa.String(length=20),
		type_=sa.String(length=13),
		existing_nullable=False,
	)
	op.drop_column("inventory_suppliers", "identification_type")
