# routers/payouts_admin.py

from typing import Optional
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from routers.auth_admin import get_current_admin
from models.orders import Order
from models.partners import Partner
from models.partner_payouts import PartnerPayout
from models.partner_payments import PartnerPayment  # ✅ NEW

router = APIRouter(
    prefix="/admin/payouts",
    tags=["Admin Payouts"],
)

# ============================
#  MODELLI Pydantic
# ============================

class PayoutCreate(BaseModel):
    partner_id: int
    order_id: int
    # ⚠️ amount lo teniamo per backward compatibility,
    # ma NON verrà più usato per scrivere in DB.
    amount: float
    note: Optional[str] = None


class PartnerPaymentCreate(BaseModel):
    partner_id: int
    amount: float
    note: Optional[str] = None


def money2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calc_commission(order_total: Decimal, commission_pct: Decimal) -> Decimal:
    return money2((order_total * commission_pct) / Decimal("100"))


# ---------------------------------------------------------
# 1️⃣ LISTA RIASSUNTIVA PAYOUT PER PARTNER
# ---------------------------------------------------------
@router.get("/by-partner")
def payouts_by_partner(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Riepilogo per ciascun partner:
    - total_generated: commissioni maturate (somma PartnerPayout.amount)
    - total_paid: pagamenti REALI effettuati (somma PartnerPayment.amount)
    - balance_due: saldo da pagare (maturato - pagato)
    """
    partners = db.query(Partner).all()
    results = []

    for p in partners:
        # ✅ totale commissioni maturate (per ordine)
        generated = (
            db.query(func.coalesce(func.sum(PartnerPayout.amount), 0))
            .filter(PartnerPayout.partner_id == p.id)
            .scalar()
        )
        generated_float = float(generated) if generated is not None else 0.0

        # ✅ totale pagamenti reali effettuati (bonifici/saldi)
        paid = (
            db.query(func.coalesce(func.sum(PartnerPayment.amount), 0))
            .filter(PartnerPayment.partner_id == p.id)
            .scalar()
        )
        paid_float = float(paid) if paid is not None else 0.0

        balance = generated_float - paid_float

        results.append(
            {
                "partner_id": p.id,
                "partner_name": getattr(p, "name", None),
                "referral_code": p.referral_code,
                "total_generated": round(generated_float, 2),
                "total_paid": round(paid_float, 2),
                "balance_due": round(balance, 2),
            }
        )

    return results


# ---------------------------------------------------------
# 2️⃣ LISTA COMMISSIONI (PartnerPayout) DI UN SINGOLO PARTNER
#    (commissioni per ordine)
# ---------------------------------------------------------
@router.get("/{partner_id}")
def partner_payout_list(
    partner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner non trovato.",
        )

    payouts = (
        db.query(PartnerPayout)
        .filter(PartnerPayout.partner_id == partner_id)
        .order_by(PartnerPayout.created_at.desc())
        .all()
    )

    return [
        {
            "id": p.id,
            "amount": float(p.amount),
            "paid": bool(p.paid),
            "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
            "order_id": getattr(p, "order_id", None),
            "note": getattr(p, "note", None),
        }
        for p in payouts
    ]


# ---------------------------------------------------------
# 2B️⃣ LISTA PAGAMENTI REALI (PartnerPayment) DI UN SINGOLO PARTNER
# ---------------------------------------------------------
@router.get("/payments/{partner_id}")
def partner_payment_list(
    partner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner non trovato.")

    payments = (
        db.query(PartnerPayment)
        .filter(PartnerPayment.partner_id == partner_id)
        .order_by(PartnerPayment.created_at.desc())
        .all()
    )

    return [
        {
            "id": p.id,
            "amount": float(p.amount),
            "note": getattr(p, "note", None),
            "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
        }
        for p in payments
    ]


# ---------------------------------------------------------
# 3️⃣ CREA PAYOUT (COMMISSIONE) LEGATO A UN ORDINE
#    🔒 IMPORTO CALCOLATO, NON INSERIBILE A MANO
# ---------------------------------------------------------
@router.post("/create")
def create_payout(
    payload: PayoutCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner_id = payload.partner_id
    order_id = payload.order_id
    note = payload.note or ""

    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner non trovato.")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato.")

    # L'ordine deve appartenere al partner
    if order.partner_id != partner_id:
        raise HTTPException(
            status_code=400,
            detail="L'ordine specificato non appartiene a questo partner.",
        )

    # ❗ Evitiamo duplicati: 1 payout per order_id
    existing = (
        db.query(PartnerPayout)
        .filter(
            PartnerPayout.partner_id == partner_id,
            PartnerPayout.order_id == order_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Payout già presente per questo ordine.",
        )

    # ✅ CALCOLO IMPORTO COMMISSIONE (ignora payload.amount)
    commission_pct = Decimal(str(partner.commission_pct))
    order_total = Decimal(str(order.total_amount))
    amount = calc_commission(order_total, commission_pct)

    payout = PartnerPayout(
        partner_id=partner_id,
        order_id=order_id,
        amount=amount,
        paid=False,
    )

    if hasattr(PartnerPayout, "note"):
        setattr(payout, "note", note)

    db.add(payout)
    db.commit()
    db.refresh(payout)

    return {
        "message": "Payout (commissione) registrato.",
        "payout_id": payout.id,
        "amount": float(payout.amount),
        "partner_id": partner_id,
        "order_id": getattr(payout, "order_id", None),
        "paid": bool(getattr(payout, "paid", False)),
        "note": getattr(payout, "note", None),
    }


# ---------------------------------------------------------
# 4️⃣ CREA PAGAMENTO REALE PARTNER (bonifico/saldo)
# ---------------------------------------------------------
@router.post("/payments/create")
def create_partner_payment(
    payload: PartnerPaymentCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner_id = payload.partner_id
    amount = Decimal(str(payload.amount))
    note = (payload.note or "").strip() or None

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Importo pagamento non valido.")

    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner non trovato.")

    payment = PartnerPayment(
        partner_id=partner_id,
        amount=money2(amount),
        note=note,
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "message": "Pagamento partner registrato.",
        "payment_id": payment.id,
        "partner_id": partner_id,
        "amount": float(payment.amount),
        "note": payment.note,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
    }
