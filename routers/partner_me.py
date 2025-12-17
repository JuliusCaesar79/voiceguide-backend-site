from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from decimal import Decimal

from app.db import get_db
from app.security import decode_access_token
from models.partners import Partner
from models.orders import Order
from models.partner_payouts import PartnerPayout
from schemas.partner_dashboard import (
    PartnerOrderItem,
    PartnerPayoutItem,
    PartnerSummary,
)

# Schema di sicurezza: semplice Bearer Token
bearer_scheme = HTTPBearer()

router = APIRouter(prefix="/partner/me", tags=["Partner Dashboard"])


def get_current_partner(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Partner:
    # Il token vero e proprio (senza "Bearer ") è in credentials.credentials
    token = credentials.credentials
    partner_id = decode_access_token(token)

    if not partner_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto.",
        )

    partner = db.query(Partner).filter(Partner.id == int(partner_id)).first()
    if not partner or not partner.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Partner non trovato o non attivo.",
        )

    return partner


@router.get("/orders", response_model=list[PartnerOrderItem])
def get_my_orders(
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .filter(Order.partner_id == current_partner.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    items = [
        PartnerOrderItem(
            order_id=o.id,
            total_amount=o.total_amount,
            payment_status=o.payment_status.value,
            created_at=o.created_at,
        )
        for o in orders
    ]
    return items


@router.get("/payouts", response_model=list[PartnerPayoutItem])
def get_my_payouts(
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
):
    payouts = (
        db.query(PartnerPayout)
        .filter(PartnerPayout.partner_id == current_partner.id)
        .order_by(PartnerPayout.created_at.desc())
        .all()
    )

    items = [
        PartnerPayoutItem(
            order_id=p.order_id,
            amount=p.amount,
            paid=p.paid,
            created_at=p.created_at,
        )
        for p in payouts
    ]
    return items


@router.get("/summary", response_model=PartnerSummary)
def get_my_summary(
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
):
    payouts = (
        db.query(PartnerPayout)
        .filter(PartnerPayout.partner_id == current_partner.id)
        .all()
    )

    total_orders = (
        db.query(Order).filter(Order.partner_id == current_partner.id).count()
    )

    total_commission = sum((p.amount for p in payouts), Decimal("0"))
    total_paid = sum((p.amount for p in payouts if p.paid), Decimal("0"))
    total_unpaid = total_commission - total_paid

    return PartnerSummary(
        total_orders=total_orders,
        total_commission=total_commission,
        total_paid=total_paid,
        total_unpaid=total_unpaid,
    )
