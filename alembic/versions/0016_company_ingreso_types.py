"""add enabled ingreso types to company config

Revision ID: 0016_company_ingreso_types
Revises: 0015_supplier_ident_type
Create Date: 2026-07-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0016_company_ingreso_types"
down_revision = "0015_supplier_ident_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_config",
        sa.Column(
            "enabled_ingreso_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"purchase\", \"initial_inventory\"]'::jsonb"),
        ),
    )
    op.execute(
        "UPDATE company_config SET enabled_ingreso_types = '[\"purchase\", \"initial_inventory\"]'::jsonb WHERE enabled_ingreso_types IS NULL"
    )
    op.alter_column(
        "company_config",
        "enabled_ingreso_types",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("company_config", "enabled_ingreso_types")