"""create order_billing_details on postgres

Revision ID: 5d1498e6da74
Revises: 75a31617731f
Create Date: 2025-12-13 18:49:09.470213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5d1498e6da74"
down_revision: Union[str, Sequence[str], None] = "75a31617731f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "order_billing_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("request_invoice", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("vat_number", sa.String(length=32), nullable=True),
        sa.Column("tax_code", sa.String(length=32), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("zip_code", sa.String(length=20), nullable=True),
        sa.Column("province", sa.String(length=50), nullable=True),
        sa.Column("pec", sa.String(length=255), nullable=True),
        sa.Column("sdi_code", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("order_billing_details")
