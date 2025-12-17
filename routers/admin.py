# routers/admin.py

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from models.partners import Partner
from models.orders import Order, OrderType, PaymentStatus
from schemas.partners import PartnerOut
from routers.auth_admin import get_current_admin

router = APIRouter(
    prefix="/admin",
    tags=["Admin Panel"],
)


# -------------------------------------------------
# GET /admin/partners → Lista completa dei partner
# -------------------------------------------------
@router.get("/partners", response_model=List[PartnerOut])
def admin_list_partners(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partners = db.query(Partner).all()
    return partners


# -------------------------------------------------
# GET /admin/orders → Report avanzato ordini
# -------------------------------------------------
@router.get("/orders")
def admin_list_orders(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Report avanzato degli ordini.

    - Filtri opzionali per data (from_date, to_date) sul campo created_at
    - Risposta strutturata:
        {
          "items": [...],
          "total_count": n,
          "from_date": "...",
          "to_date": "...",
          "total_amount": x.xx,
          "total_estimated_agora_cost": y.yy,
          "total_margin": z.zz
        }
    """

    query = db.query(Order)

    # Filtri data su created_at
    if from_date:
        start_dt = datetime.combine(from_date, datetime.min.time())
        query = query.filter(Order.created_at >= start_dt)

    if to_date:
        end_dt = datetime.combine(to_date + timedelta(days=1), datetime.min.time())
        query = query.filter(Order.created_at < end_dt)

    # Ordiniamo dal più recente
    query = query.order_by(Order.created_at.desc())

    orders = query.all()

    items = []
    total_amount = 0.0
    total_estimated_agora_cost = 0.0
    total_margin = 0.0

    for o in orders:
        amount_float = float(o.total_amount) if o.total_amount is not None else 0.0
        total_amount += amount_float

        estimated_agora_cost = (
            float(o.estimated_agora_cost) if o.estimated_agora_cost is not None else None
        )

        # Margine lordo: prezzo cliente - costo stimato Agora (solo se presente)
        margin = None
        if estimated_agora_cost is not None:
            margin = amount_float - estimated_agora_cost
            total_estimated_agora_cost += estimated_agora_cost
            total_margin += margin

        item = {
            "id": o.id,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "buyer_email": o.buyer_email,
            "buyer_whatsapp": o.buyer_whatsapp,
            "order_type": o.order_type.value if o.order_type else None,
            "package_id": o.package_id,
            "quantity": o.quantity,
            "total_amount": amount_float,
            "estimated_agora_cost": estimated_agora_cost,
            "margin": margin,
            "payment_method": o.payment_method.value if o.payment_method else None,
            "payment_status": o.payment_status.value if o.payment_status else None,
            "partner_id": o.partner_id,
            "referral_code": o.referral_code,
        }
        items.append(item)

    response = {
        "items": items,
        "total_count": len(items),
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "total_amount": round(total_amount, 2),
        "total_estimated_agora_cost": round(total_estimated_agora_cost, 2),
        "total_margin": round(total_margin, 2),
    }

    return response


# -------------------------------------------------
# GET /admin/orders/{order_id} → Dettaglio singolo ordine
# -------------------------------------------------
@router.get("/orders/{order_id}")
def admin_get_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Restituisce il dettaglio di un singolo ordine.
    """

    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ordine con id={order_id} non trovato.",
        )

    amount_float = float(order.total_amount) if order.total_amount is not None else 0.0
    estimated_agora_cost = (
        float(order.estimated_agora_cost) if order.estimated_agora_cost is not None else None
    )
    margin = None
    if estimated_agora_cost is not None:
        margin = amount_float - estimated_agora_cost

    return {
        "id": order.id,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "buyer_email": order.buyer_email,
        "buyer_whatsapp": order.buyer_whatsapp,
        "order_type": order.order_type.value if order.order_type else None,
        "package_id": order.package_id,
        "quantity": order.quantity,
        "total_amount": amount_float,
        "estimated_agora_cost": estimated_agora_cost,
        "margin": margin,
        "payment_method": order.payment_method.value if order.payment_method else None,
        "payment_status": order.payment_status.value if order.payment_status else None,
        "partner_id": order.partner_id,
        "referral_code": order.referral_code,
    }


# -------------------------------------------------
# GET /admin/stats/overview → Statistiche globali ordini
# -------------------------------------------------
@router.get("/stats/overview")
def admin_stats_overview(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Restituisce una panoramica generale delle statistiche sugli ordini:
    - numero totale di ordini
    - totale economico complessivo
    - totale costo Agora stimato
    - margine totale
    - conteggio per tipo ordine
    - conteggio per stato pagamento
    """

    # Totale ordini e totale economico
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    total_amount_decimal = db.query(func.coalesce(func.sum(Order.total_amount), 0)).scalar()
    total_amount = float(total_amount_decimal) if total_amount_decimal is not None else 0.0

    # Totale costo Agora stimato
    total_agora_decimal = db.query(func.coalesce(func.sum(Order.estimated_agora_cost), 0)).scalar()
    total_estimated_agora_cost = (
        float(total_agora_decimal) if total_agora_decimal is not None else 0.0
    )

    # Margine totale
    total_margin = total_amount - total_estimated_agora_cost

    # Conteggio ordini per tipo
    orders_by_type: Dict[str, int] = {t.value: 0 for t in OrderType}
    rows_type = (
        db.query(Order.order_type, func.count(Order.id))
        .group_by(Order.order_type)
        .all()
    )
    for order_type, count in rows_type:
        if order_type is not None:
            orders_by_type[order_type.value] = count

    # Conteggio ordini per stato pagamento
    orders_by_status: Dict[str, int] = {s.value: 0 for s in PaymentStatus}
    rows_status = (
        db.query(Order.payment_status, func.count(Order.id))
        .group_by(Order.payment_status)
        .all()
    )
    for status, count in rows_status:
        if status is not None:
            orders_by_status[status.value] = count

    return {
        "total_orders": total_orders,
        "total_amount": round(total_amount, 2),
        "total_estimated_agora_cost": round(total_estimated_agora_cost, 2),
        "total_margin": round(total_margin, 2),
        "orders_by_type": orders_by_type,
        "orders_by_status": orders_by_status,
    }
