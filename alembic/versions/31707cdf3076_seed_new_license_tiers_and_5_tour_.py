"""seed new license tiers and 5 tour bundle packages

Revision ID: 31707cdf3076
Revises: 9497449e48ad
Create Date: 2026-09-11 18:58:04.373741

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31707cdf3076'
down_revision: Union[str, Sequence[str], None] = '9497449e48ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


packages = sa.table(
    "packages",
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("package_type", sa.String),
    sa.column("num_licenses", sa.Integer),
    sa.column("max_guests", sa.Integer),
    sa.column("price", sa.Numeric),
    sa.column("is_active", sa.Boolean),
)

NEW_SINGLE_ROWS = [
    {
        "name": "Licenza singola — 5 partecipanti",
        "description": "1 sessione di tour fino a 5 ospiti. Attivazione immediata.",
        "package_type": "SINGLE",
        "num_licenses": 1,
        "max_guests": 5,
        "price": 3.99,
        "is_active": True,
    },
    {
        "name": "Licenza singola — 15 partecipanti",
        "description": "1 sessione di tour fino a 15 ospiti. Attivazione immediata.",
        "package_type": "SINGLE",
        "num_licenses": 1,
        "max_guests": 15,
        "price": 9.99,
        "is_active": True,
    },
    {
        "name": "Licenza singola — 50 partecipanti",
        "description": "1 sessione di tour fino a 50 ospiti. Attivazione immediata.",
        "package_type": "SINGLE",
        "num_licenses": 1,
        "max_guests": 50,
        "price": 27.99,
        "is_active": True,
    },
]

# "5 Tour": stesso package_type='TO' dei pacchetti Tour Operator esistenti
# (stesso sconto partner), num_licenses=5 fisso, max_guests variabile.
NEW_BUNDLE5_ROWS = [
    {
        "name": "Pacchetto 5 Tour — 25 partecipanti a licenza",
        "description": "5 licenze incluse, 25 ospiti per licenza.",
        "package_type": "TO",
        "num_licenses": 5,
        "max_guests": 25,
        "price": 59.99,
        "is_active": True,
    },
    {
        "name": "Pacchetto 5 Tour — 35 partecipanti a licenza",
        "description": "5 licenze incluse, 35 ospiti per licenza.",
        "package_type": "TO",
        "num_licenses": 5,
        "max_guests": 35,
        "price": 79.99,
        "is_active": True,
    },
    {
        "name": "Pacchetto 5 Tour — 50 partecipanti a licenza",
        "description": "5 licenze incluse, 50 ospiti per licenza.",
        "package_type": "TO",
        "num_licenses": 5,
        "max_guests": 50,
        "price": 111.99,
        "is_active": True,
    },
]

OLD_10_PRICE = "7.99"
NEW_10_PRICE = "6.99"


def upgrade() -> None:
    op.bulk_insert(packages, NEW_SINGLE_ROWS)
    op.bulk_insert(packages, NEW_BUNDLE5_ROWS)

    # Taglio da 10 ospiti: resta attivo, riprezzato per coerenza con i nuovi
    # tagli 5 (3.99) e 15 (9.99) che gli stanno intorno.
    op.execute(
        sa.text(
            "UPDATE packages SET price = :new_price "
            "WHERE package_type = 'SINGLE' AND num_licenses = 1 AND max_guests = 10"
        ).bindparams(new_price=NEW_10_PRICE)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE packages SET price = :old_price "
            "WHERE package_type = 'SINGLE' AND num_licenses = 1 AND max_guests = 10"
        ).bindparams(old_price=OLD_10_PRICE)
    )

    op.execute(
        "DELETE FROM packages WHERE package_type = 'TO' AND num_licenses = 5 "
        "AND max_guests IN (25, 35, 50)"
    )
    op.execute(
        "DELETE FROM packages WHERE package_type = 'SINGLE' AND num_licenses = 1 "
        "AND max_guests IN (5, 15, 50)"
    )
