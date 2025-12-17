"""fix partner_requests partner_type nullable

Revision ID: 758431d85461
Revises: d8df00fc4db5
Create Date: 2025-12-13 20:19:41.823401
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "758431d85461"
down_revision: Union[str, Sequence[str], None] = "d8df00fc4db5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    q = sa.text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = :t
          AND column_name = :c
        """
    )
    return bind.execute(q, {"t": table, "c": column}).first() is not None


def upgrade() -> None:
    """
    Legacy safety migration:
    - if partner_requests.partner_type exists:
        - set default 'BASE'
        - make it nullable
    - if it does NOT exist (newer schema), do nothing
    """
    if not _column_exists("partner_requests", "partner_type"):
        return

    op.execute(
        "ALTER TABLE partner_requests "
        "ALTER COLUMN partner_type SET DEFAULT 'BASE'"
    )

    op.alter_column(
        "partner_requests",
        "partner_type",
        existing_type=sa.Enum("BASE", "PRO", "ELITE", name="partnertype"),
        nullable=True,
        existing_nullable=False,
    )


def downgrade() -> None:
    if not _column_exists("partner_requests", "partner_type"):
        return

    op.alter_column(
        "partner_requests",
        "partner_type",
        existing_type=sa.Enum("BASE", "PRO", "ELITE", name="partnertype"),
        nullable=False,
        existing_nullable=True,
    )

    op.execute(
        "ALTER TABLE partner_requests "
        "ALTER COLUMN partner_type DROP DEFAULT"
    )
