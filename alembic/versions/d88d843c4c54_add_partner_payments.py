"""add partner payments

Revision ID: d88d843c4c54
Revises: 33c8f0c22a06
Create Date: 2025-12-12 16:45:57.745620
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d88d843c4c54"
down_revision: Union[str, Sequence[str], None] = "33c8f0c22a06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Crea la tabella partner_payments.

    Questa tabella rappresenta i PAGAMENTI REALI effettuati al partner
    (bonifici, contanti, saldo manuale).
    È volutamente separata da partner_payouts che rappresenta invece
    le COMMISSIONI maturate per ordine.
    """
    op.create_table(
        "partner_payments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "partner_id",
            sa.Integer(),
            sa.ForeignKey("partners.id"),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
        ),
        sa.Column(
            "note",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        op.f("ix_partner_payments_id"),
        "partner_payments",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_partner_payments_id"),
        table_name="partner_payments",
    )
    op.drop_table("partner_payments")
