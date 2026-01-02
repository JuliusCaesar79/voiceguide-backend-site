# routers/stripe_webhook.py

from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_UP

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from models.orders import Order, PaymentMethod, PaymentStatus

# ✅ Fulfillment: genera licenza + invia email
try:
    from app.fulfillment_service import fulfill_paid_order  # type: ignore
except Exception:
    fulfill_paid_order = None  # type: ignore


router = APIRouter(tags=["Webhooks"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def _money2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _eur_to_cents(amount_eur: Decimal) -> int:
    a = _money2(amount_eur)
    return int((a * 100).to_integral_value(rounding=ROUND_HALF_UP))


async def _handle_stripe_webhook(request: Request, db: Session) -> dict:
    """
    Stripe webhook handler.
    - Verifica firma con STRIPE_WEBHOOK_SECRET
    - checkout.session.completed:
        - prova a recuperare ordine con:
          1) metadata.order_id (se presente)
          2) stripe_session_id == session.id (fallback)
          3) stripe_payment_intent_id == payment_intent (fallback)
        - verifica coerenza importo (anti-mapping sbagliato)
        - marca PAID
        - fulfillment (idempotente)
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
    # checkout.session.completed (main)
    # -----------------------------------
    if event_type == "checkout.session.completed":
        session_obj = event["data"]["object"]

        session_id = session_obj.get("id")
        metadata = session_obj.get("metadata") or {}
        order_id_raw = metadata.get("order_id")

        amount_total = session_obj.get("amount_total")  # cents
        currency = (session_obj.get("currency") or "").lower()
        payment_intent = session_obj.get("payment_intent")

        order = None

        # 1) Lookup by metadata.order_id (preferred)
        if order_id_raw:
            try:
                order_id = int(order_id_raw)
                order = db.query(Order).filter(Order.id == order_id).first()
            except Exception:
                order = None

        # 2) Fallback by stripe_session_id == session.id
        if not order and session_id and hasattr(Order, "stripe_session_id"):
            try:
                order = db.query(Order).filter(getattr(Order, "stripe_session_id") == session_id).first()
            except Exception:
                order = None

        # 3) Fallback by stripe_payment_intent_id == payment_intent
        if not order and payment_intent and hasattr(Order, "stripe_payment_intent_id"):
            try:
                order = db.query(Order).filter(getattr(Order, "stripe_payment_intent_id") == payment_intent).first()
            except Exception:
                order = None

        if not order:
            print(
                "[stripe_webhook] IGNORE order not found | "
                f"metadata.order_id={order_id_raw} session_id={session_id} payment_intent={payment_intent}"
            )
            return {"ok": True, "ignored": "order not found"}

        # ✅ Guard-rail: verify Stripe amount matches order.total_amount
        try:
            expected_total = Decimal(str(order.total_amount))
            expected_cents = _eur_to_cents(expected_total)
        except Exception:
            print(f"[stripe_webhook] ERROR cannot parse order.total_amount for order_id={order.id}")
            return {"ok": True, "ignored": "invalid order amount"}

        if isinstance(amount_total, int):
            if amount_total != expected_cents:
                print(
                    "[stripe_webhook] AMOUNT MISMATCH -> NOT MARKING PAID | "
                    f"order_id={order.id} expected_cents={expected_cents} "
                    f"stripe_amount_total={amount_total} currency={currency} session_id={session_id}"
                )
                return {
                    "ok": True,
                    "ignored": "amount_mismatch",
                    "order_id": order.id,
                    "expected_cents": expected_cents,
                    "stripe_amount_total": amount_total,
                    "currency": currency,
                    "session_id": session_id,
                }
        else:
            print(
                f"[stripe_webhook] WARN missing/invalid amount_total in session for order_id={order.id} session_id={session_id}"
            )

        was_paid = (order.payment_status == PaymentStatus.PAID)

        if not was_paid:
            # set payment info
            try:
                order.payment_method = PaymentMethod.STRIPE
            except Exception:
                pass
            order.payment_status = PaymentStatus.PAID

            # store stripe IDs if fields exist
            if hasattr(order, "stripe_session_id") and session_id:
                try:
                    order.stripe_session_id = session_id
                except Exception:
                    pass

            if hasattr(order, "stripe_payment_intent_id") and payment_intent:
                try:
                    order.stripe_payment_intent_id = payment_intent
                except Exception:
                    pass

            db.add(order)
            db.commit()
            db.refresh(order)

        # ✅ Fulfillment ALWAYS (idempotent)
        if fulfill_paid_order:
            try:
                fulfill_paid_order(db=db, order=order, stripe_session=session_obj)
            except Exception as e:
                print(f"[stripe_webhook] fulfill_paid_order ERROR for order_id={order.id}: {e}")

        return {
            "ok": True,
            "order_id": order.id,
            "status": "PAID",
            "was_already_paid": was_paid,
            "fulfillment_enabled": bool(fulfill_paid_order),
            "session_id": session_id,
            "payment_intent": payment_intent,
        }

    # (optional) You can add other event types later if needed
    return {"ok": True, "ignored": event_type}


# ✅ NEW: matches your Stripe webhook URL
@router.post("/stripe/webhook")
async def stripe_webhook_new(request: Request, db: Session = Depends(get_db)):
    return await _handle_stripe_webhook(request, db)


# ✅ LEGACY: keep compatibility with old path
@router.post("/webhooks/stripe")
async def stripe_webhook_legacy(request: Request, db: Session = Depends(get_db)):
    return await _handle_stripe_webhook(request, db)
