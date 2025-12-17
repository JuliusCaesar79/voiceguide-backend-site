"""merge heads final

Revision ID: 9497449e48ad
Revises: 547c2f19efba, 68c05add70ff
Create Date: 2025-12-16 17:29:57.855314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9497449e48ad'
down_revision: Union[str, Sequence[str], None] = ('547c2f19efba', '68c05add70ff')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
