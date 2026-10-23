"""add language to partner_requests and partners (email partner in 5 lingue)

Revision ID: a6d4e1f08c32
Revises: f3c81d27a9b4
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6d4e1f08c32"
down_revision: Union[str, Sequence[str], None] = "f3c81d27a9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("partner_requests", sa.Column("language", sa.String(length=5), nullable=True))
    op.add_column("partners", sa.Column("language", sa.String(length=5), nullable=True))


def downgrade() -> None:
    op.drop_column("partners", "language")
    op.drop_column("partner_requests", "language")
