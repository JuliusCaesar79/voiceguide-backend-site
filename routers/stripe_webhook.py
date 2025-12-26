# routers/stripe_webhook.py

from __future__ import annotations

import os
import stripe

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from models.orders import Order, PaymentMethod, PaymentStatus

# ✅ Fulfillment: genera licenza + invia email (Resend)
try:
    from app.fulfillment_service import fulfill_paid_order  # type: ignore
except Exception:
    fulfill_paid_order = None  # type: ignore

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook endpoint.
    - Verifica firma con STRIPE_WEBHOOK_SECRET
    - Gestisce checkout.session.completed -> set Order PAID
    - Poi chiama fulfillment (licenza + email) SEMPRE (idempotente)
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Stripe webhook not configured (missing STRIPE_WEBHOOK_SECRET)",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {str(e)}")

    event_type = event.get("type")

    # -----------------------------------
    # checkout.session.completed
    # -----------------------------------
    if event_type == "checkout.session.completed":
        session_obj = event["data"]["object"]
        metadata = session_obj.get("metadata") or {}
        order_id_raw = metadata.get("order_id")

        if not order_id_raw:
            return {"ok": True, "ignored": "missing order_id metadata"}

        try:
            order_id = int(order_id_raw)
        except Exception:
            return {"ok": True, "ignored": "invalid order_id metadata"}

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"ok": True, "ignored": "order not found"}

        # Se NON è pagato, lo segniamo pagato
        was_paid = (order.payment_status == PaymentStatus.PAID)

        if not was_paid:
            try:
                order.payment_method = PaymentMethod.STRIPE
            except Exception:
                pass
            order.payment_status = PaymentStatus.PAID

            # campi extra opzionali (se esistono nel model)
            if hasattr(order, "stripe_session_id"):
                try:
                    order.stripe_session_id = session_obj.get("id")
                except Exception:
                    pass

            if hasattr(order, "stripe_payment_intent_id"):
                try:
                    order.stripe_payment_intent_id = session_obj.get("payment_intent")
                except Exception:
                    pass

            db.add(order)
            db.commit()
            db.refresh(order)

        # ✅ Fulfillment SEMPRE (idempotente): anche se era già PAID
        if fulfill_paid_order:
            try:
                fulfill_paid_order(db=db, order=order, stripe_session=session_obj)
            except Exception as e:
                # Stripe vuole comunque 200: logghiamo per debug
                print(f"[stripe_webhook] fulfill_paid_order ERROR for order_id={order.id}: {e}")

        return {
            "ok": True,
            "order_id": order.id,
            "status": "PAID",
            "was_already_paid": was_paid,
            "fulfillment_enabled": bool(fulfill_paid_order),
        }

    return {"ok": True, "ignored": event_type}
