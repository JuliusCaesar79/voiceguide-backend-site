# routers/stripe_webhook.py

from __future__ import annotations

import os
import stripe

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from models.orders import Order, PaymentMethod, PaymentStatus

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
    """
    if not STRIPE_WEBHOOK_SECRET:
        # meglio fallire chiaramente: senza secret non accettiamo webhook
        raise HTTPException(status_code=500, detail="Stripe webhook not configured (missing STRIPE_WEBHOOK_SECRET)")

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
        # firma non valida o payload malformato
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {str(e)}")

    event_type = event.get("type")

    # -----------------------------------
    # 1) checkout.session.completed
    # -----------------------------------
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]

        # Metadata impostata in /checkout/stripe/session
        metadata = session.get("metadata") or {}
        order_id_raw = metadata.get("order_id")

        if not order_id_raw:
            # niente da fare: non sappiamo a quale ordine collegarlo
            return {"ok": True, "ignored": "missing order_id metadata"}

        try:
            order_id = int(order_id_raw)
        except Exception:
            return {"ok": True, "ignored": "invalid order_id metadata"}

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"ok": True, "ignored": "order not found"}

        # idempotenza: se già pagato, ok
        if order.payment_status == PaymentStatus.PAID:
            return {"ok": True, "status": "already_paid"}

        # segna pagato
        try:
            order.payment_method = PaymentMethod.STRIPE
        except Exception:
            pass

        order.payment_status = PaymentStatus.PAID

        # se esistono campi extra nel model, li valorizziamo senza rompere
        if hasattr(order, "stripe_session_id"):
            try:
                order.stripe_session_id = session.get("id")
            except Exception:
                pass

        if hasattr(order, "stripe_payment_intent_id"):
            try:
                order.stripe_payment_intent_id = session.get("payment_intent")
            except Exception:
                pass

        if hasattr(order, "paid_at"):
            # se hai un campo datetime paid_at, Stripe non manda timestamp “paid_at” qui;
            # lo mettiamo a "now" via DB default o qui se gestisci tu. Per ora non forziamo.
            pass

        db.add(order)
        db.commit()
        db.refresh(order)

        return {"ok": True, "order_id": order.id, "status": "PAID"}

    # -----------------------------------
    # altri eventi: per ora ignoriamo
    # -----------------------------------
    return {"ok": True, "ignored": event_type}
