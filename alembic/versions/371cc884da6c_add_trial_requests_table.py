"""add trial_requests table

Revision ID: 371cc884da6c
Revises: eaa684c0bbd7
Create Date: 2025-12-15 20:01:23.628676
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "371cc884da6c"
down_revision: Union[str, Sequence[str], None] = "eaa684c0bbd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUM_NAME = "trial_request_status"
ENUM_VALUES = ("PENDING", "ISSUED", "REJECTED")


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # 1) Create enum type ONLY if it does not exist (idempotent)
    op.execute(f"""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{ENUM_NAME}') THEN
            CREATE TYPE {ENUM_NAME} AS ENUM ('{ENUM_VALUES[0]}','{ENUM_VALUES[1]}','{ENUM_VALUES[2]}');
        END IF;
    END$$;
    """)

    # 2) If table already exists, stop here (idempotent)
    tables = set(insp.get_table_names(schema="public"))
    if "trial_requests" in tables:
        return

    # IMPORTANT: create_type=False prevents SQLAlchemy from trying CREATE TYPE again
    trial_request_status = sa.Enum(
        *ENUM_VALUES,
        name=ENUM_NAME,
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
    bind = op.get_bind()
    insp = inspect(bind)

    tables = set(insp.get_table_names(schema="public"))
    if "trial_requests" in tables:
        op.drop_index("ix_trial_requests_status", table_name="trial_requests")
        op.drop_index("ix_trial_requests_email", table_name="trial_requests")
        op.drop_table("trial_requests")

    # Drop enum type ONLY if exists (idempotent)
    op.execute(f"""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = '{ENUM_NAME}') THEN
            DROP TYPE {ENUM_NAME};
        END IF;
    END$$;
    """)
