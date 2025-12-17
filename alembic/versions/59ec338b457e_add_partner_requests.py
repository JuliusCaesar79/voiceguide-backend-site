"""add partner_requests

Revision ID: 59ec338b457e
Revises: c1130bbbeed8
Create Date: 2025-12-13 19:10:39.718192
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "59ec338b457e"
down_revision: Union[str, Sequence[str], None] = "c1130bbbeed8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ENUM partner_tier ---
    op.execute("""
    DO $$
    BEGIN
        CREATE TYPE partner_tier AS ENUM ('BASE', 'PRO', 'ELITE');
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END$$;
    """)

    # --- ENUM partner_request_status ---
    op.execute("""
    DO $$
    BEGIN
        CREATE TYPE partner_request_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END$$;
    """)

    partner_tier = postgresql.ENUM("BASE", "PRO", "ELITE", name="partner_tier", create_type=False)
    partner_request_status = postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="partner_request_status", create_type=False)

    op.create_table(
        "partner_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("partner_tier", partner_tier, nullable=False, server_default=sa.text("'BASE'")),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("status", partner_request_status, nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # email unica (come nel model)
    op.create_unique_constraint("uq_partner_requests_email", "partner_requests", ["email"])
    op.create_index("ix_partner_requests_id", "partner_requests", ["id"])


def downgrade() -> None:
    op.drop_index("ix_partner_requests_id", table_name="partner_requests")
    op.drop_constraint("uq_partner_requests_email", "partner_requests", type_="unique")
    op.drop_table("partner_requests")
