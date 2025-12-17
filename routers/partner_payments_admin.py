# routers/partner_payments_admin.py

from typing import Optional, List
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from routers.auth_admin import get_current_admin
from models.partners import Partner
from models.partner_payments import PartnerPayment


router = APIRouter(
    prefix="/admin/partner-payments",
    tags=["Admin Partner Payments"],
)


# ============================
#  Pydantic Schemas
# ============================

class PartnerPaymentCreate(BaseModel):
    partner_id: int
    amount: Decimal
    note: Optional[str] = None


def money2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------
# 1) LISTA PAGAMENTI REALI DI UN PARTNER
# ---------------------------------------------------------
@router.get("/{partner_id}")
def list_partner_payments(
    partner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner non trovato.")

    payments = (
        db.query(PartnerPayment)
        .filter(PartnerPayment.partner_id == partner_id)
        .order_by(PartnerPayment.created_at.desc())
        .all()
    )

    return [
        {
            "id": p.id,
            "partner_id": p.partner_id,
            "amount": float(p.amount),
            "note": p.note,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in payments
    ]


# ---------------------------------------------------------
# 2) RIEPILOGO PAGAMENTI PER PARTNER
# ---------------------------------------------------------
@router.get("/by-partner")
def payments_by_partner(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Ritorna per ciascun partner:
    - total_paid: somma PartnerPayment.amount
    - payments_count: numero pagamenti registrati
    """
    rows = (
        db.query(
            Partner.id.label("partner_id"),
            Partner.name.label("partner_name"),
            Partner.referral_code.label("referral_code"),
            func.coalesce(func.sum(PartnerPayment.amount), 0).label("total_paid"),
            func.count(PartnerPayment.id).label("payments_count"),
        )
        .outerjoin(PartnerPayment, PartnerPayment.partner_id == Partner.id)
        .group_by(Partner.id, Partner.name, Partner.referral_code)
        .order_by(Partner.id.asc())
        .all()
    )

    return [
        {
            "partner_id": int(r.partner_id),
            "partner_name": r.partner_name,
            "referral_code": r.referral_code,
            "total_paid": float(r.total_paid or 0),
            "payments_count": int(r.payments_count or 0),
        }
        for r in rows
    ]


# ---------------------------------------------------------
# 3) CREA PAGAMENTO REALE (BONIFICO/CONTANTI/SALDO)
# ---------------------------------------------------------
@router.post("/create")
def create_partner_payment(
    payload: PartnerPaymentCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner = db.query(Partner).filter(Partner.id == payload.partner_id).first()
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner non trovato.")

    amount = money2(Decimal(str(payload.amount)))
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Importo non valido.")

    payment = PartnerPayment(
        partner_id=payload.partner_id,
        amount=amount,
        note=(payload.note or "").strip() or None,
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "message": "Pagamento partner registrato.",
        "payment_id": payment.id,
        "partner_id": payment.partner_id,
        "amount": float(payment.amount),
        "note": payment.note,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
    }
