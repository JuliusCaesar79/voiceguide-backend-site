# routers/admin.py

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
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


def _serialize_billing_details(order: Order) -> Dict[str, Any]:
    """
    Serializza i dati di fatturazione (se presenti) in modo stabile.
    Non richiede modifiche al DB: usa Order.billing_details (1:1).
    """
    bd = getattr(order, "billing_details", None)

    # Se non esiste record, oppure request_invoice = False → fattura non richiesta
    if not bd or not getattr(bd, "request_invoice", False):
        return {
            "invoice_requested": False,
            "invoice_intestatario": None,
            "invoice_country": None,
            "billing_details": None,
        }

    billing_details = {
        "request_invoice": bool(bd.request_invoice),
        "country": bd.country,
        # company_name = INTESTATARIO (persona o azienda)
        "company_name": bd.company_name,
        "vat_number": bd.vat_number,
        "tax_code": bd.tax_code,
        "address": bd.address,
        "city": bd.city,
        "zip_code": bd.zip_code,
        "province": bd.province,
        "pec": bd.pec,
        "sdi_code": bd.sdi_code,
        "created_at": bd.created_at.isoformat() if bd.created_at else None,
        "updated_at": bd.updated_at.isoformat() if bd.updated_at else None,
    }

    return {
        "invoice_requested": True,
        "invoice_intestatario": bd.company_name,
        "invoice_country": bd.country,
        "billing_details": billing_details,
    }


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

    ✅ Aggiunte:
    - invoice_requested (bool)
    - invoice_intestatario (str|null)
    - invoice_country (str|null)
    - billing_details (object|null)  <-- dettagli completi per UI admin
    """
    query = (
        db.query(Order)
        .options(joinedload(Order.billing_details))  # ✅ carica fatturazione
    )

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

    items: List[Dict[str, Any]] = []
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

        billing = _serialize_billing_details(o)

        item: Dict[str, Any] = {
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

            # ✅ campi fatturazione (riassunto + dettagli completi)
            "invoice_requested": billing["invoice_requested"],
            "invoice_intestatario": billing["invoice_intestatario"],
            "invoice_country": billing["invoice_country"],
            "billing_details": billing["billing_details"],
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
    Include anche i dettagli fatturazione (se richiesti).
    """
    order = (
        db.query(Order)
        .options(joinedload(Order.billing_details))  # ✅ carica fatturazione
        .filter(Order.id == order_id)
        .first()
    )

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

    billing = _serialize_billing_details(order)

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

        # ✅ fatturazione
        "invoice_requested": billing["invoice_requested"],
        "invoice_intestatario": billing["invoice_intestatario"],
        "invoice_country": billing["invoice_country"],
        "billing_details": billing["billing_details"],
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
