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

    Make migration safe on BOTH:
    - existing DBs where partner_type exists
    - fresh DBs where partner_type may NOT exist yet

    Actions:
    - ensure column exists (if missing, add it with default BASE)
    - set default 'BASE'
    - make column nullable (so inserts without partner_type won't fail)
    """

    # 0) Ensure the column exists (fresh-db-safe)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'partner_requests'
                  AND column_name = 'partner_type'
            ) THEN
                ALTER TABLE partner_requests
                ADD COLUMN partner_type VARCHAR NOT NULL DEFAULT 'BASE';
            END IF;
        END $$;
        """
    )

    # 1) Set DEFAULT BASE (idempotent)
    op.execute(
        "ALTER TABLE partner_requests "
        "ALTER COLUMN partner_type SET DEFAULT 'BASE'"
    )

    # 2) Make nullable so inserts that don't provide partner_type won't fail
    # Use VARCHAR here to avoid enum-type dependency issues on fresh DBs
    op.alter_column(
        "partner_requests",
        "partner_type",
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    # revert nullable change (only if column exists)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'partner_requests'
                  AND column_name = 'partner_type'
            ) THEN
                ALTER TABLE partner_requests
                ALTER COLUMN partner_type SET NOT NULL;
                ALTER TABLE partner_requests
                ALTER COLUMN partner_type DROP DEFAULT;
            END IF;
        END $$;
        """
    )
