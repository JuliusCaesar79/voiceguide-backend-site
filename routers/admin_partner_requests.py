# routers/admin_partner_requests.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from decimal import Decimal
import uuid
import logging

from app.db import get_db

from models.partner_requests import (
    PartnerRequest,
    PartnerRequestStatus,
    PartnerTier,
)
from models.partners import Partner

from schemas.partner_requests import PartnerRequestOut

# EMAIL SERVICE (app/email_service.py)
from app.email_service import (
    send_partner_request_approved_email,
    send_partner_request_rejected_email,
)

router = APIRouter(prefix="/admin/partner-requests", tags=["Admin - Partner Requests"])

logger = logging.getLogger(__name__)

# -------------------------------------------------
# TIER → COMMISSION DEFAULT
# -------------------------------------------------
TIER_DEFAULT_COMMISSION: dict[str, Decimal] = {
    "BASE": Decimal("10.0"),
    "PRO": Decimal("15.0"),
    "ELITE": Decimal("20.0"),
}


def generate_referral_code() -> str:
    # Codice corto, leggibile (es: VG-AB12CD)
    raw = uuid.uuid4().hex[:6].upper()
    return f"VG-{raw}"


def normalize_tier(tier_obj) -> str:
    """
    tier_obj può essere:
    - PartnerTier enum (req.partner_tier)
    - stringa
    """
    if tier_obj is None:
        return "BASE"

    # Enum -> .value
    if hasattr(tier_obj, "value"):
        val = tier_obj.value
    else:
        val = str(tier_obj)

    val = str(val).strip().upper()
    return val if val in TIER_DEFAULT_COMMISSION else "BASE"


@router.get("", response_model=list[PartnerRequestOut])
def list_partner_requests(
    status: PartnerRequestStatus | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(PartnerRequest)
    if status:
        q = q.filter(PartnerRequest.status == status)
    return q.order_by(PartnerRequest.id.desc()).all()


@router.post("/{request_id}/reject", response_model=PartnerRequestOut)
def reject_partner_request(request_id: int, db: Session = Depends(get_db)):
    req = db.query(PartnerRequest).filter(PartnerRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")

    if req.status != PartnerRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not PENDING.")

    req.status = PartnerRequestStatus.REJECTED
    db.add(req)
    db.commit()
    db.refresh(req)

    # ---- invio email (NON BLOCCANTE) ----
    try:
        send_partner_request_rejected_email(
            to_email=req.email,
            partner_name=req.name,
        )
    except Exception as e:
        logger.warning(
            "Email REJECT fallita per request_id=%s (%s): %s",
            request_id,
            req.email,
            str(e),
        )

    return req


@router.post("/{request_id}/approve", response_model=PartnerRequestOut)
def approve_partner_request(
    request_id: int,
    tier: str | None = Query(default=None),
    commission_pct: Decimal | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Approva la richiesta e crea un Partner attivo con referral_code.

    - tier (query): BASE/PRO/ELITE (se passato, ha priorità sul tier salvato nella request)
    - Default: commissione derivata dal tier (BASE 10 / PRO 15 / ELITE 20)
    - Override: passando commission_pct in query
    """
    req = db.query(PartnerRequest).filter(PartnerRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")

    if req.status != PartnerRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not PENDING.")

    # ---- tier scelto dall'admin (se presente) ----
    chosen_tier = normalize_tier(tier) if tier else normalize_tier(req.partner_tier)

    # Salva il tier scelto sulla request (tracciamento definitivo)
    # partner_tier è Enum PartnerTier: settiamo in modo corretto
    req.partner_tier = PartnerTier[chosen_tier]

    # ---- commissione di default dal tier ----
    default_comm = TIER_DEFAULT_COMMISSION[chosen_tier]
    final_commission = commission_pct if commission_pct is not None else default_comm

    # safety clamp (0-100)
    if final_commission < Decimal("0") or final_commission > Decimal("100"):
        raise HTTPException(
            status_code=400, detail="commission_pct must be between 0 and 100."
        )

    # ---- referral code ----
    code = generate_referral_code()
    while db.query(Partner).filter(Partner.referral_code == code).first():
        code = generate_referral_code()

    # ---- crea Partner ----
    partner = Partner(
        name=req.name,
        email=req.email,
        referral_code=code,
        commission_pct=final_commission,
        is_active=True,
    )
    db.add(partner)

    # ---- aggiorna richiesta ----
    req.status = PartnerRequestStatus.APPROVED
    db.add(req)

    db.commit()
    db.refresh(req)

    # ---- invio email (NON BLOCCANTE) ----
    try:
        send_partner_request_approved_email(
            to_email=req.email,
            partner_name=req.name,
            referral_code=code,
            commission_pct=str(final_commission),
            tier=str(chosen_tier),
        )
    except Exception as e:
        logger.warning(
            "Email APPROVE fallita per request_id=%s (%s): %s",
            request_id,
            req.email,
            str(e),
        )

    return req
