"""add baja reason and company baja reasons

Revision ID: 0018_baja_reason_and_config
Revises: 0017_company_egreso_types
Create Date: 2026-07-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0018_baja_reason_and_config"
down_revision = "0017_company_egreso_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_config",
        sa.Column(
            "enabled_baja_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                "'[\"damage\", \"expiration\", \"loss\", \"theft\", \"donation\", \"gift\", \"destruction\", \"sample\", \"other\"]'::jsonb"
            ),
        ),
    )
    op.execute(
        "UPDATE company_config SET enabled_baja_reasons = '[\"damage\", \"expiration\", \"loss\", \"theft\", \"donation\", \"gift\", \"destruction\", \"sample\", \"other\"]'::jsonb WHERE enabled_baja_reasons IS NULL"
    )
    op.alter_column(
        "company_config",
        "enabled_baja_reasons",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=None,
    )
    op.add_column(
        "inventory_documents",
        sa.Column("baja_reason", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_documents", "baja_reason")
    op.drop_column("company_config", "enabled_baja_reasons")
