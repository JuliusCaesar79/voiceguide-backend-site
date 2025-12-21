"""fix partner_requests partner_type nullable

Revision ID: 758431d85461
Revises: d8df00fc4db5
Create Date: 2025-12-13 20:19:41.823401
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "758431d85461"
down_revision: Union[str, Sequence[str], None] = "d8df00fc4db5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Legacy safety migration.
    If the table/column doesn't exist (fresh DB / new schema), do NOTHING.
    """
    bind = op.get_bind()
    insp = inspect(bind)

    tables = set(insp.get_table_names(schema="public"))
    if "partner_requests" not in tables:
        return

    cols = {c["name"] for c in insp.get_columns("partner_requests", schema="public")}
    if "partner_type" not in cols:
        return

    # 1) set DEFAULT BASE (legacy safety)
    op.execute(
        "ALTER TABLE partner_requests "
        "ALTER COLUMN partner_type SET DEFAULT 'BASE'"
    )

    # 2) make nullable
    op.alter_column(
        "partner_requests",
        "partner_type",
        existing_type=sa.Enum("BASE", "PRO", "ELITE", name="partnertype"),
        nullable=True,
        existing_nullable=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    tables = set(insp.get_table_names(schema="public"))
    if "partner_requests" not in tables:
        return

    cols = {c["name"] for c in insp.get_columns("partner_requests", schema="public")}
    if "partner_type" not in cols:
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
