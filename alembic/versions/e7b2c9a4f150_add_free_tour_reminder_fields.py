"""add reminder_sent_at / emails_opt_out_at to free_tour_signups

Revision ID: e7b2c9a4f150
Revises: d2a8e6b41f57
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b2c9a4f150"
down_revision: Union[str, Sequence[str], None] = "d2a8e6b41f57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("free_tour_signups", sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("free_tour_signups", sa.Column("emails_opt_out_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("free_tour_signups", "emails_opt_out_at")
    op.drop_column("free_tour_signups", "reminder_sent_at")
