"""add enabled egreso types to company config

Revision ID: 0017_company_egreso_types
Revises: 0016_company_ingreso_types
Create Date: 2026-07-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0017_company_egreso_types"
down_revision = "0016_company_ingreso_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_config",
        sa.Column(
            "enabled_egreso_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                "'[\"sale\", \"adjustment_negative\", \"supplier_return\", \"damage_disposal\", \"expiration_disposal\", \"loss_theft_disposal\", \"donation\", \"internal_consumption\", \"transfer_sent\", \"other\"]'::jsonb"
            ),
        ),
    )
    op.execute(
        "UPDATE company_config SET enabled_egreso_types = '[\"sale\", \"adjustment_negative\", \"supplier_return\", \"damage_disposal\", \"expiration_disposal\", \"loss_theft_disposal\", \"donation\", \"internal_consumption\", \"transfer_sent\", \"other\"]'::jsonb WHERE enabled_egreso_types IS NULL"
    )
    op.alter_column(
        "company_config",
        "enabled_egreso_types",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("company_config", "enabled_egreso_types")
