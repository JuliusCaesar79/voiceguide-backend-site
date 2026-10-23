# models/free_tour_signups.py

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from models import Base


class FreeTourSignup(Base):
    """
    Registrazione sul sito con email + codice di 6 cifre: chi conferma riceve
    3 licenze gratuite (5, 25, 35 ospiti), una sola volta per email.

    Ogni richiesta di codice crea una riga; la riga confermata ha verified_at
    e claimed_email valorizzati. claimed_email e' UNIQUE: due conferme per la
    stessa email (anche in contemporanea) non possono passare entrambe.
    """

    __tablename__ = "free_tour_signups"

    id = Column(Integer, primary_key=True)

    # Email come l'ha scritta l'utente (per inviare) e normalizzata
    # (minuscole, senza +tag, senza punti per Gmail) per i controlli.
    email = Column(String(255), nullable=False)
    email_normalized = Column(String(255), nullable=False, index=True)
    language = Column(String(5), nullable=False, default="it")

    code_hash = Column(String(64), nullable=False)
    code_expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)

    ip_address = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    claimed_email = Column(String(255), nullable=True, unique=True)

    # Codici emessi, separati da virgola (es. "VG-LIC-AAAA,VG-LIC-BBBB,...")
    license_codes = Column(Text, nullable=True)
