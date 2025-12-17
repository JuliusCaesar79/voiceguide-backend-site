"""update partner_requests

Revision ID: bd7190d4db68
Revises: 371cc884da6c
Create Date: 2025-12-16 15:35:46.919120
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bd7190d4db68"
down_revision: Union[str, Sequence[str], None] = "371cc884da6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) updated_at
    op.add_column(
        "partner_requests",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 2) email unique index (manteniamo l'index email come unique)
    #    (se esiste già un index non-unique, lo rimpiazziamo)
    op.drop_index("ix_partner_requests_email", table_name="partner_requests")
    op.create_index(
        "ix_partner_requests_email",
        "partner_requests",
        ["email"],
        unique=True,
    )

    # 3) rimozione vecchio campo legacy (se esiste nel DB)
    #    Nota: se la tua tabella non ha partner_type, questo darà errore.
    #    Se hai dubbi, lo rendiamo condizionale dopo con un check.
    op.drop_column("partner_requests", "partner_type")

    # 4) Enum status: gestiamo rename in modo sicuro
    #    Se nel DB esiste il vecchio enum "partnerrequeststatus", facciamo:
    #    - rename type -> partner_request_status
    #    - aggiorniamo la colonna a usare il nuovo nome
    op.execute("ALTER TYPE partnerrequeststatus RENAME TO partner_request_status")

    op.alter_column(
        "partner_requests",
        "status",
        existing_type=postgresql.ENUM(
            "PENDING", "APPROVED", "REJECTED", name="partnerrequeststatus"
        ),
        type_=postgresql.ENUM(
            "PENDING", "APPROVED", "REJECTED", name="partner_request_status"
        ),
        existing_nullable=False,
        server_default=sa.text("'PENDING'"),
    )


def downgrade() -> None:
    # Revert enum name
    op.execute("ALTER TYPE partner_request_status RENAME TO partnerrequeststatus")

    # Revert status column
    op.alter_column(
        "partner_requests",
        "status",
        existing_type=postgresql.ENUM(
            "PENDING", "APPROVED", "REJECTED", name="partner_request_status"
        ),
        type_=postgresql.ENUM(
            "PENDING", "APPROVED", "REJECTED", name="partnerrequeststatus"
        ),
        existing_nullable=False,
        server_default=sa.text("'PENDING'"),
    )

    # Re-add partner_type (legacy)
    op.add_column(
        "partner_requests",
        sa.Column("partner_type", sa.String(length=255), nullable=True),
    )

    # Revert email index to non-unique
    op.drop_index("ix_partner_requests_email", table_name="partner_requests")
    op.create_index(
        "ix_partner_requests_email",
        "partner_requests",
        ["email"],
        unique=False,
    )

    # Drop updated_at
    op.drop_column("partner_requests", "updated_at")
