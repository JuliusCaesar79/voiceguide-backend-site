from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from schemas.partners import PartnerCreate, PartnerOut
from models.partners import Partner, PartnerType

router = APIRouter(prefix="/partners", tags=["Partners"])


@router.post("/create", response_model=PartnerOut)
def create_partner(payload: PartnerCreate, db: Session = Depends(get_db)):

    # Controllo email duplicata
    existing_email = db.query(Partner).filter(Partner.email == payload.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email già registrata come partner.")

    # Controllo referral duplicato
    existing_ref = db.query(Partner).filter(Partner.referral_code == payload.referral_code).first()
    if existing_ref:
        raise HTTPException(status_code=400, detail="Referral code già in uso.")

    # Conversione partner type
    try:
        partner_type = PartnerType(payload.partner_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="partner_type deve essere BASE, PRO o ELITE.")

    partner = Partner(
        name=payload.name,
        email=payload.email,
        partner_type=partner_type,
        commission_pct=payload.commission_pct,
        referral_code=payload.referral_code,
        notes=payload.notes,
        is_active=True
    )

    db.add(partner)
    db.commit()
    db.refresh(partner)

    return partner


@router.get("/", response_model=list[PartnerOut])
def list_partners(db: Session = Depends(get_db)):
    return db.query(Partner).all()
