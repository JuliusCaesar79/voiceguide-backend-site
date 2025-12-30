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

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def _money2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _eur_to_cents(amount_eur: Decimal) -> int:
    a = _money2(amount_eur)
    return int((a * 100).to_integral_value(rounding=ROUND_HALF_UP))


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook endpoint.
    - Verifica firma con STRIPE_WEBHOOK_SECRET
    - checkout.session.completed:
        - recupera order_id da metadata (obbligatorio)
        - ✅ verifica coerenza importo (anti-mapping sbagliato)
        - marca PAID solo se coerente
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
    # checkout.session.completed
    # -----------------------------------
    if event_type == "checkout.session.completed":
        session_obj = event["data"]["object"]

        session_id = session_obj.get("id")
        metadata = session_obj.get("metadata") or {}
        order_id_raw = metadata.get("order_id")

        # Stripe amount_total è in centesimi (int)
        amount_total = session_obj.get("amount_total")
        currency = (session_obj.get("currency") or "").lower()

        if not order_id_raw:
            # IMPORTANTISSIMO: senza order_id non processiamo (evita mapping random)
            print(f"[stripe_webhook] IGNORE missing metadata.order_id session_id={session_id}")
            return {"ok": True, "ignored": "missing order_id metadata"}

        try:
            order_id = int(order_id_raw)
        except Exception:
            print(f"[stripe_webhook] IGNORE invalid metadata.order_id={order_id_raw} session_id={session_id}")
            return {"ok": True, "ignored": "invalid order_id metadata"}

        # 1) Lookup principale: per ID
        order = db.query(Order).filter(Order.id == order_id).first()

        # 2) Fallback: se non trovato e abbiamo stripe_session_id nel model, proviamo per session.id
        if not order and session_id and hasattr(Order, "stripe_session_id"):
            try:
                order = db.query(Order).filter(getattr(Order, "stripe_session_id") == session_id).first()
            except Exception:
                order = None

        if not order:
            print(f"[stripe_webhook] IGNORE order not found order_id={order_id} session_id={session_id}")
            return {"ok": True, "ignored": "order not found"}

        # ✅ Guard-rail anti-errore: verifica che l'importo di Stripe combaci con order.total_amount
        # Se il webhook sta colpendo un DB diverso, qui blocchiamo il disastro (14.99 non può pagare 119).
        try:
            expected_total = Decimal(str(order.total_amount))
            expected_cents = _eur_to_cents(expected_total)
        except Exception:
            print(f"[stripe_webhook] ERROR cannot parse order.total_amount for order_id={order.id}")
            return {"ok": True, "ignored": "invalid order amount"}

        # Se Stripe non manda amount_total (raro), non blocchiamo ma logghiamo.
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

        # Se NON è pagato, lo segniamo pagato
        was_paid = (order.payment_status == PaymentStatus.PAID)

        if not was_paid:
            try:
                order.payment_method = PaymentMethod.STRIPE
            except Exception:
                pass
            order.payment_status = PaymentStatus.PAID

            # campi extra opzionali (se esistono nel model)
            if hasattr(order, "stripe_session_id") and session_id:
                try:
                    order.stripe_session_id = session_id
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
            "session_id": session_id,
        }

    return {"ok": True, "ignored": event_type}
