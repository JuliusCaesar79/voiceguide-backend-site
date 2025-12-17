# app/deps_partner.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from models.partners import Partner
from app.security import decode_access_token

# Estrae il token dall'header Authorization: Bearer <token>
oauth2_scheme_partner = OAuth2PasswordBearer(tokenUrl="/partner/login")


def get_current_partner(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme_partner),
) -> Partner:
    """
    Restituisce il Partner corrente partendo dal token JWT.
    Accetta SOLO token in cui il campo 'sub' è un id numerico di partner.
    Se il token non è valido, scaduto, o non numerico → 401.
    """
    partner_id = decode_access_token(token)

    # Token non valido o senza sub
    if partner_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token partner non valido o scaduto.",
        )

    # Se il sub NON è un numero (es. 'admin:1'), rifiutiamo
    if not str(partner_id).isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido per accesso partner.",
        )

    partner_id_int = int(partner_id)

    partner = (
        db.query(Partner)
        .filter(Partner.id == partner_id_int, Partner.is_active == True)  # noqa: E712
        .first()
    )

    if not partner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Partner non trovato o non attivo.",
        )

    return partner
