"""add requested_max_guests to trial_requests

Revision ID: b31dc90b7ae8
Revises: 31707cdf3076
Create Date: 2026-09-11 19:30:00.809401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b31dc90b7ae8'
down_revision: Union[str, Sequence[str], None] = '31707cdf3076'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trial_requests",
        sa.Column("requested_max_guests", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trial_requests", "requested_max_guests")
