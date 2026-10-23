"""add followup_sent_at to free_tour_signups

Revision ID: f3c81d27a9b4
Revises: e7b2c9a4f150
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3c81d27a9b4"
down_revision: Union[str, Sequence[str], None] = "e7b2c9a4f150"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("free_tour_signups", sa.Column("followup_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("free_tour_signups", "followup_sent_at")
