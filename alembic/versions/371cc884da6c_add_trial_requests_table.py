"""add trial_requests table

Revision ID: 371cc884da6c
Revises: eaa684c0bbd7
Create Date: 2025-12-15 20:01:23.628676
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "371cc884da6c"
down_revision: Union[str, Sequence[str], None] = "eaa684c0bbd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ✅ SUPER ROBUST: crea il tipo solo se NON esiste
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'trial_request_status') THEN
            CREATE TYPE trial_request_status AS ENUM ('PENDING', 'ISSUED', 'REJECTED');
          END IF;
        END$$;
        """
    )

    # Usa il tipo esistente, senza tentare di ricrearlo
    trial_request_status = sa.Enum(
        "PENDING",
        "ISSUED",
        "REJECTED",
        name="trial_request_status",
        create_type=False,
    )

    op.create_table(
        "trial_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False, server_default="it"),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column(
            "status",
            trial_request_status,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index("ix_trial_requests_email", "trial_requests", ["email"])
    op.create_index("ix_trial_requests_status", "trial_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_trial_requests_status", table_name="trial_requests")
    op.drop_index("ix_trial_requests_email", table_name="trial_requests")
    op.drop_table("trial_requests")

    # Non droppiamo forzatamente il TYPE in downgrade (potrebbe essere usato altrove)
    # Se vuoi, possiamo aggiungere un drop condizionale più avanti.
