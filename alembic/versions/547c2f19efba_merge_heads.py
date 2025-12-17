"""merge heads

Revision ID: 547c2f19efba
Revises: 5d1498e6da74, bd7190d4db68
Create Date: 2025-12-16 17:22:16.271572

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '547c2f19efba'
down_revision: Union[str, Sequence[str], None] = ('5d1498e6da74', 'bd7190d4db68')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
