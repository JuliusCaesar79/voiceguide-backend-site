"""add_manual_trial_fields_to_licenses

Revision ID: eaa684c0bbd7
Revises: 758431d85461
Create Date: 2025-12-14 21:22:00.884956

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "eaa684c0bbd7"
down_revision: Union[str, Sequence[str], None] = "758431d85461"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) order_id -> nullable True (per licenze manual/trial senza ordine)
    op.alter_column(
        "licenses",
        "order_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 2) nuove colonne (tutte nullable, non rompono nulla)
    op.add_column("licenses", sa.Column("issued_to_email", sa.String(length=255), nullable=True))
    op.add_column("licenses", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("licenses", sa.Column("issued_by_admin", sa.String(length=255), nullable=True))

    # 3) indice utile per ricerche/lista trial/manual
    op.create_index("ix_licenses_issued_to_email", "licenses", ["issued_to_email"], unique=False)


def downgrade() -> None:
    # NB: se hai creato licenze trial con order_id NULL, il downgrade potrebbe fallire
    # perché riportiamo order_id a NOT NULL. In tal caso, prima aggiorna/elimina quelle righe.

    op.drop_index("ix_licenses_issued_to_email", table_name="licenses")

    op.drop_column("licenses", "issued_by_admin")
    op.drop_column("licenses", "notes")
    op.drop_column("licenses", "issued_to_email")

    op.alter_column(
        "licenses",
        "order_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
