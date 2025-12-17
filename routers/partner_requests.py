# routers/partner_requests.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from models.partner_requests import PartnerRequest, PartnerRequestStatus
from schemas.partner_requests import PartnerRequestCreate, PartnerRequestOut

router = APIRouter(prefix="/partner-requests", tags=["Partner Requests"])


@router.post("", response_model=PartnerRequestOut)
def create_partner_request(payload: PartnerRequestCreate, db: Session = Depends(get_db)):
    # Anti-duplicati: stessa email con richiesta ancora PENDING
    existing = (
        db.query(PartnerRequest)
        .filter(
            PartnerRequest.email == str(payload.email).lower().strip(),
            PartnerRequest.status == PartnerRequestStatus.PENDING,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="A request for this email is already pending.",
        )

    req = PartnerRequest(
        name=payload.name.strip(),
        email=str(payload.email).lower().strip(),
        partner_tier=payload.partner_tier.value,  # <-- DB ENUM partner_tier
        notes=(payload.notes.strip() if payload.notes else None),
        status=PartnerRequestStatus.PENDING,
    )

    db.add(req)
    db.commit()
    db.refresh(req)
    return req
