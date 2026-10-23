"""add orders.language (lingua del cliente per le email)

Revision ID: d2a8e6b41f57
Revises: c4f7a2d91e03
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2a8e6b41f57"
down_revision: Union[str, Sequence[str], None] = "c4f7a2d91e03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("language", sa.String(length=5), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "language")
