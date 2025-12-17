"""fix partner_requests partner_type nullable

Revision ID: 758431d85461
Revises: d8df00fc4db5
Create Date: 2025-12-13 20:19:41.823401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "758431d85461"
down_revision: Union[str, Sequence[str], None] = "d8df00fc4db5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix legacy column partner_type (NOT NULL) that blocks inserts
    after we introduced partner_tier.
    - set default 'BASE'
    - make partner_type nullable
    """

    # 1) set DEFAULT BASE (legacy safety)
    op.execute(
        "ALTER TABLE partner_requests "
        "ALTER COLUMN partner_type SET DEFAULT 'BASE'"
    )

    # 2) make nullable so inserts that don't provide partner_type won't fail
    op.alter_column(
        "partner_requests",
        "partner_type",
        existing_type=sa.Enum("BASE", "PRO", "ELITE", name="partnertype"),
        nullable=True,
        existing_nullable=False,
    )


def downgrade() -> None:
    # revert nullable change
    op.alter_column(
        "partner_requests",
        "partner_type",
        existing_type=sa.Enum("BASE", "PRO", "ELITE", name="partnertype"),
        nullable=False,
        existing_nullable=True,
    )

    # remove default
    op.execute(
        "ALTER TABLE partner_requests "
        "ALTER COLUMN partner_type DROP DEFAULT"
    )
