"""add 'voided' document status (distinct from 'cancelled')

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-08
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 'cancelled' = a pending document that was cancelled (never took effect).
    # 'voided'    = an approved document that was annulled (effect reversed).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'voided'")

    # Reclassify documents annulled before this distinction existed: those were
    # stored as 'cancelled' but the audit trail flags them as voids.
    op.execute(
        """
        UPDATE inventory_documents d SET status = 'voided'
        WHERE d.status = 'cancelled' AND EXISTS (
            SELECT 1 FROM audit_logs a
            WHERE a.entity_type = 'inventory_document'
              AND a.entity_id = d.id::text
              AND a.action = 'CANCEL'
              AND (a.new_values ->> 'voided') = 'true'
        )
        """
    )


def downgrade() -> None:
    # Enum values can't be dropped in PostgreSQL without recreating the type.
    # Revert voided documents to 'cancelled' so the value is left unused.
    op.execute(
        "UPDATE inventory_documents SET status = 'cancelled' WHERE status = 'voided'"
    )
