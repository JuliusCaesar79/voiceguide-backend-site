"""update partner_requests

Revision ID: bd7190d4db68
Revises: 371cc884da6c
Create Date: 2025-12-16 15:35:46.919120
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "bd7190d4db68"
down_revision: Union[str, Sequence[str], None] = "371cc884da6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "partner_requests"
SCHEMA = "public"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # ---- columns ----
    cols = {c["name"] for c in insp.get_columns(TABLE, schema=SCHEMA)}

    # 1) updated_at (add only if missing)
    if "updated_at" not in cols:
        op.add_column(
            TABLE,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )

    # 2) email unique index
    indexes = {i["name"] for i in insp.get_indexes(TABLE, schema=SCHEMA)}
    if "ix_partner_requests_email" in indexes:
        op.drop_index("ix_partner_requests_email", table_name=TABLE, schema=SCHEMA)

    op.create_index(
        "ix_partner_requests_email",
        TABLE,
        ["email"],
        unique=True,
        schema=SCHEMA,
    )

    # 3) drop legacy partner_type only if exists
    if "partner_type" in cols:
        op.drop_column(TABLE, "partner_type", schema=SCHEMA)

    # ---- enum status rename (safe) ----
    res = bind.execute(
        sa.text(
            """
            SELECT typname
            FROM pg_type
            WHERE typname IN ('partnerrequeststatus', 'partner_request_status')
            """
        )
    ).fetchall()

    enum_names = {r[0] for r in res}

    # rename enum only if old exists and new does not
    if "partnerrequeststatus" in enum_names and "partner_request_status" not in enum_names:
        op.execute(
            "ALTER TYPE partnerrequeststatus RENAME TO partner_request_status"
        )

    # ensure column uses new enum name
    op.alter_column(
        TABLE,
        "status",
        existing_type=postgresql.ENUM(
            "PENDING", "APPROVED", "REJECTED", name="partnerrequeststatus"
        ),
        type_=postgresql.ENUM(
            "PENDING", "APPROVED", "REJECTED", name="partner_request_status"
        ),
        existing_nullable=False,
        server_default=sa.text("'PENDING'"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    cols = {c["name"] for c in insp.get_columns(TABLE, schema=SCHEMA)}
    indexes = {i["name"] for i in insp.get_indexes(TABLE, schema=SCHEMA)}

    # revert enum name if needed
    res = bind.execute(
        sa.text(
            """
            SELECT typname
            FROM pg_type
            WHERE typname IN ('partnerrequeststatus', 'partner_request_status')
            """
        )
    ).fetchall()

    enum_names = {r[0] for r in res}

    if "partner_request_status" in enum_names and "partnerrequeststatus" not in enum_names:
        op.execute(
            "ALTER TYPE partner_request_status RENAME TO partnerrequeststatus"
        )

    # revert status column
    op.alter_column(
        TABLE,
        "status",
        existing_type=postgresql.ENUM(
            "PENDING", "APPROVED", "REJECTED", name="partner_request_status"
        ),
        type_=postgresql.ENUM(
            "PENDING", "APPROVED", "REJECTED", name="partnerrequeststatus"
        ),
        existing_nullable=False,
        server_default=sa.text("'PENDING'"),
        schema=SCHEMA,
    )

    # re-add partner_type if missing
    if "partner_type" not in cols:
        op.add_column(
            TABLE,
            sa.Column("partner_type", sa.String(length=255), nullable=True),
            schema=SCHEMA,
        )

    # revert email index to non-unique
    if "ix_partner_requests_email" in indexes:
        op.drop_index("ix_partner_requests_email", table_name=TABLE, schema=SCHEMA)

    op.create_index(
        "ix_partner_requests_email",
        TABLE,
        ["email"],
        unique=False,
        schema=SCHEMA,
    )

    # drop updated_at if exists
    if "updated_at" in cols:
        op.drop_column(TABLE, "updated_at", schema=SCHEMA)
