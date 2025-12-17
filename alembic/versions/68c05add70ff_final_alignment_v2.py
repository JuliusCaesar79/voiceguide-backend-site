"""final alignment v2

Revision ID: 68c05add70ff
Revises: bd7190d4db68
Create Date: 2025-12-16 15:55:48.844203
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "68c05add70ff"
down_revision: Union[str, Sequence[str], None] = "bd7190d4db68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rimuove indice inutile sul PK (id)
    op.drop_index(op.f("ix_licenses_id"), table_name="licenses")


def downgrade() -> None:
    # Ripristina l'indice (solo se si fa downgrade)
    op.create_index(op.f("ix_licenses_id"), "licenses", ["id"], unique=False)
