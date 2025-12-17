from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from models.partners import Partner
from schemas.auth import PartnerLoginRequest, TokenResponse
from app.security import create_access_token

router = APIRouter(prefix="/partner", tags=["Partner Auth"])


@router.post("/login", response_model=TokenResponse)
def partner_login(payload: PartnerLoginRequest, db: Session = Depends(get_db)):
    partner = (
        db.query(Partner)
        .filter(
            Partner.email == payload.email,
            Partner.referral_code == payload.referral_code,
            Partner.is_active == True,   # noqa: E712
        )
        .first()
    )

    if not partner:
        raise HTTPException(status_code=401, detail="Credenziali partner non valide.")

    access_token = create_access_token({"sub": str(partner.id)})

    return TokenResponse(access_token=access_token)
