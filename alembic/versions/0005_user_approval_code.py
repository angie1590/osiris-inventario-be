"""add user approval code hash

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("approval_code_hash", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "approval_code_hash")
