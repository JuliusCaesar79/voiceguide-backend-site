# routers/partner_portal.py
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps_partner import get_current_partner
from models.partners import Partner
from models.orders import Order, OrderType, PaymentStatus
from models.partner_payouts import PartnerPayout
from models.partner_payments import PartnerPayment  # ✅ NEW
from models.licenses import License

router = APIRouter(prefix="/partner", tags=["Partner Portal"])


def _build_partner_level_label(partner: Partner) -> str:
    try:
        pct = float(partner.commission_pct or 0)
    except Exception:
        pct = 0.0

    type_label = partner.partner_type.value if partner.partner_type else "BASE"
    return f"{type_label} ({pct:.0f}%)"


@router.get("/me")
def partner_me(
    current_partner: Partner = Depends(get_current_partner),
):
    return {
        "id": current_partner.id,
        "name": current_partner.name,
        "email": current_partner.email,
        "referral_code": current_partner.referral_code,
        "partner_type": current_partner.partner_type.value
        if current_partner.partner_type
        else None,
        "commission_pct": float(current_partner.commission_pct or 0),
        "partner_level": _build_partner_level_label(current_partner),
        "is_active": current_partner.is_active,
        "created_at": current_partner.created_at,
    }


@router.get("/summary")
def partner_summary(
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
):
    """
    Riepilogo economico partner (CORRETTO):

    - total_generated  = commissioni maturate (PartnerPayout)
    - total_paid       = pagamenti ricevuti (PartnerPayment)
    - balance_due      = saldo disponibile
    - total_commission = alias legacy di total_generated
    - pending_commission = alias legacy di balance_due
    """
    partner_id = current_partner.id

    # =========================
    # COMMISSIONI MATURATE
    # =========================
    total_generated = (
        db.query(func.coalesce(func.sum(PartnerPayout.amount), 0))
        .filter(PartnerPayout.partner_id == partner_id)
        .scalar()
        or Decimal("0")
    )

    # =========================
    # PAGAMENTI RICEVUTI
    # =========================
    total_paid = (
        db.query(func.coalesce(func.sum(PartnerPayment.amount), 0))
        .filter(PartnerPayment.partner_id == partner_id)
        .scalar()
        or Decimal("0")
    )

    # =========================
    # SALDO DISPONIBILE
    # =========================
    balance_due = total_generated - total_paid

    # =========================
    # ORDINI / LICENZE
    # =========================
    total_orders = (
        db.query(func.count(Order.id))
        .filter(Order.partner_id == partner_id)
        .scalar()
        or 0
    )

    total_licenses_sold = (
        db.query(func.count(License.id))
        .join(Order, License.order_id == Order.id)
        .filter(Order.partner_id == partner_id)
        .scalar()
        or 0
    )

    return {
        # ✅ NUOVI CAMPI (USATI DALLA DASHBOARD)
        "total_generated": float(total_generated),
        "total_paid": float(total_paid),
        "balance_due": float(balance_due),

        # ⚠️ LEGACY (per compatibilità)
        "total_commission": float(total_generated),
        "pending_commission": float(balance_due),

        # METADATA
        "total_orders": int(total_orders),
        "total_licenses_sold": int(total_licenses_sold),
        "partner_type": current_partner.partner_type.value
        if current_partner.partner_type
        else None,
        "commission_pct": float(current_partner.commission_pct or 0),
        "partner_level": _build_partner_level_label(current_partner),
    }


@router.get("/orders")
def partner_orders(
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
):
    partner_id = current_partner.id

    rows = (
        db.query(
            Order.id,
            Order.created_at,
            Order.order_type,
            Order.total_amount,
            Order.payment_status,
            func.coalesce(func.sum(PartnerPayout.amount), 0).label("commission_amount"),
            func.bool_or(PartnerPayout.paid).label("payout_paid"),
        )
        .outerjoin(PartnerPayout, PartnerPayout.order_id == Order.id)
        .filter(Order.partner_id == partner_id)
        .group_by(
            Order.id,
            Order.created_at,
            Order.order_type,
            Order.total_amount,
            Order.payment_status,
        )
        .order_by(Order.created_at.desc())
        .all()
    )

    def build_product_label(order_type: OrderType) -> str:
        if order_type == OrderType.SINGLE:
            return "Licenza singola VoiceGuide AirLink"
        elif order_type == OrderType.PACKAGE_TO:
            return "Pacchetto Tour Operator"
        elif order_type == OrderType.PACKAGE_SCHOOL:
            return "Pacchetto Scuole"
        elif order_type == OrderType.MUSEUM:
            return "Partnership Musei"
        return "Ordine VoiceGuide AirLink"

    def build_status_label(payment_status: PaymentStatus, payout_paid: bool) -> str:
        if payment_status == PaymentStatus.PAID:
            return "paid" if payout_paid else "pending_payout"
        if payment_status == PaymentStatus.PENDING:
            return "payment_pending"
        if payment_status == PaymentStatus.FAILED:
            return "payment_failed"
        if payment_status == PaymentStatus.REFUNDED:
            return "refunded"
        return "unknown"

    result = []
    for row in rows:
        result.append(
            {
                "id": row.id,
                "created_at": row.created_at,
                "product_name": build_product_label(row.order_type),
                "license_type": row.order_type.value if row.order_type else None,
                "gross_amount": float(row.total_amount or 0),
                "commission_amount": float(row.commission_amount or 0),
                "status": build_status_label(row.payment_status, bool(row.payout_paid)),
            }
        )

    return result
