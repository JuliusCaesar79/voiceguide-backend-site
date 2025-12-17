"""add trial_requests table

Revision ID: 371cc884da6c
Revises: eaa684c0bbd7
Create Date: 2025-12-15 20:01:23.628676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "371cc884da6c"
down_revision: Union[str, Sequence[str], None] = "eaa684c0bbd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PostgreSQL enum for status
    trial_request_status = sa.Enum(
        "PENDING",
        "ISSUED",
        "REJECTED",
        name="trial_request_status",
    )
    trial_request_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "trial_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False, server_default="it"),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column(
            "status",
            trial_request_status,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index("ix_trial_requests_email", "trial_requests", ["email"])
    op.create_index("ix_trial_requests_status", "trial_requests", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_trial_requests_status", table_name="trial_requests")
    op.drop_index("ix_trial_requests_email", table_name="trial_requests")
    op.drop_table("trial_requests")

    trial_request_status = sa.Enum(
        "PENDING",
        "ISSUED",
        "REJECTED",
        name="trial_request_status",
    )
    trial_request_status.drop(op.get_bind(), checkfirst=True)
