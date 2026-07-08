"""Rename isbn_required param to barcode_required

Revision ID: 0012_rename_isbn_required_param
Revises: 0011
Create Date: 2026-07-08
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_rename_isbn_required_param"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE system_params
        SET key = 'barcode_required',
            description = 'Hace obligatorio el codigo de barras al crear/editar productos'
        WHERE key = 'isbn_required'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE system_params
        SET key = 'isbn_required',
            description = 'Hace obligatorio el ISBN al crear/editar productos'
        WHERE key = 'barcode_required'
        """
    )
