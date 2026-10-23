"""add free_tour_signups (registrazione sito con 3 licenze gratuite)

Revision ID: c4f7a2d91e03
Revises: b31dc90b7ae8
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f7a2d91e03"
down_revision: Union[str, Sequence[str], None] = "b31dc90b7ae8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "free_tour_signups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_normalized", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False, server_default="it"),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_email", sa.String(length=255), nullable=True),
        sa.Column("license_codes", sa.Text(), nullable=True),
        sa.UniqueConstraint("claimed_email", name="uq_free_tour_signups_claimed_email"),
    )
    op.create_index("ix_free_tour_signups_email_normalized", "free_tour_signups", ["email_normalized"])
    op.create_index("ix_free_tour_signups_ip_address", "free_tour_signups", ["ip_address"])
    op.create_index("ix_free_tour_signups_created_at", "free_tour_signups", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_free_tour_signups_created_at", table_name="free_tour_signups")
    op.drop_index("ix_free_tour_signups_ip_address", table_name="free_tour_signups")
    op.drop_index("ix_free_tour_signups_email_normalized", table_name="free_tour_signups")
    op.drop_table("free_tour_signups")
