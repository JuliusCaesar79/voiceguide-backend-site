"""base revision (bootstrap)

Revision ID: d053aa181db0
Revises:
Create Date: 2025-12-07 11:00:00

Questo file serve SOLO a ripristinare la catena Alembic.
Non crea né modifica nulla.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d053aa181db0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
