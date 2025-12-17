"""add partner_tier to partner_requests

Revision ID: d8df00fc4db5
Revises: 59ec338b457e
Create Date: 2025-12-13 19:50:12.758874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8df00fc4db5"
down_revision: Union[str, Sequence[str], None] = "59ec338b457e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Crea ENUM partner_tier SOLO se non esiste già
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'partner_tier') THEN
                CREATE TYPE partner_tier AS ENUM ('BASE', 'PRO', 'ELITE');
            END IF;
        END$$;
        """
    )

    # 2) Aggiunge colonna partner_tier SOLO se non esiste già
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'partner_requests'
                  AND column_name = 'partner_tier'
            ) THEN
                ALTER TABLE partner_requests
                ADD COLUMN partner_tier partner_tier NOT NULL DEFAULT 'BASE';
            END IF;
        END$$;
        """
    )

    # 3) (pulizia) rimuove il default, lasciando NOT NULL
    op.execute(
        """
        ALTER TABLE partner_requests
        ALTER COLUMN partner_tier DROP DEFAULT;
        """
    )


def downgrade() -> None:
    # In downgrade evitiamo di droppare l'ENUM se potrebbe essere usato altrove.
    # Quindi: togliamo solo la colonna.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'partner_requests'
                  AND column_name = 'partner_tier'
            ) THEN
                ALTER TABLE partner_requests
                DROP COLUMN partner_tier;
            END IF;
        END$$;
        """
    )

    # Se vuoi droppare anche l'enum in futuro, lo faremo in una migration separata
    # solo quando siamo certi che non è referenziato.
