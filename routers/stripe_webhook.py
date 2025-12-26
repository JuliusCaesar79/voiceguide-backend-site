# routers/stripe_webhook.py

from __future__ import annotations

import os
import stripe
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from models.orders import Order, PaymentMethod, PaymentStatus

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

log = logging.getLogger("stripe_webhook")
log.setLevel(logging.INFO)

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def _safe_get(d: Dict[str, Any], path: str, default=None):
    """
    path es: "data.object.id"
    """
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
    return cur if cur is not None else default


def _extract_order_id_from_session(session: Dict[str, Any]) -> Optional[int]:
    metadata = session.get("metadata") or {}
    raw = metadata.get("order_id")
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _maybe_send_payment_email(order: Order) -> None:
    """
    Email nostra “pagamento ricevuto”.
    Se non esiste la funzione, non rompiamo il webhook: logghiamo e fine.
    """
    try:
        # Se in app/email_service.py esiste, la useremo.
        from app.email_service import send_payment_received_email  # type: ignore
    except Exception:
        log.info("Email: send_payment_received_email non presente -> skip")
        return

    try:
        send_payment_received_email(
            to_email=order.buyer_email,
            order_id=order.id,
            payment_method="STRIPE",
        )
        log.info("Email: pagamento ricevuto inviata. order_id=%s", order.id)
    except Exception as e:
        log.exception("Email pagamento fallita. order_id=%s err=%s", order.id, str(e))


def _maybe_fulfill_license(order: Order) -> None:
    """
    Hook di fulfillment (creazione licenza + invio licenza).
    In questa campagna lo attacchiamo qui.
    Se non esiste ancora la funzione, non rompiamo: logghiamo e fine.
    """
    try:
        # Nome suggerito: lo creeremo noi nel prossimo passo.
        from app.fulfillment import fulfill_paid_order  # type: ignore
    except Exception:
        log.info("Fulfillment: fulfill_paid_order non presente -> skip")
        return

    try:
        fulfill_paid_order(order_id=order.id)
        log.info("Fulfillment: eseguito. order_id=%s", order.id)
    except Exception as e:
        log.exception("Fulfillment fallito. order_id=%s err=%s", order.id, str(e))


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook endpoint.
    - Verifica firma con STRIPE_WEBHOOK_SECRET
    - Gestisce checkout.session.completed -> set Order PAID + fulfillment hook + email
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
    log.info("Stripe webhook ricevuto: type=%s id=%s", event_type, event.get("id"))

    # -----------------------------------
    # checkout.session.completed
    # -----------------------------------
    if event_type == "checkout.session.completed":
        session = _safe_get(event, "data.object", default={}) or {}

        order_id = _extract_order_id_from_session(session)
        if not order_id:
            log.warning("checkout.session.completed senza metadata.order_id -> ignored")
            return {"ok": True, "ignored": "missing order_id metadata"}

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            log.warning("Ordine non trovato. order_id=%s -> ignored", order_id)
            return {"ok": True, "ignored": "order not found"}

        # IDempotenza: se già pagato non rifacciamo nulla (ma rispondiamo 200)
        if order.payment_status == PaymentStatus.PAID:
            log.info("Ordine già PAID. order_id=%s -> already_paid", order_id)
            return {"ok": True, "order_id": order.id, "status": "already_paid"}

        # Segna pagato
        order.payment_method = PaymentMethod.STRIPE
        order.payment_status = PaymentStatus.PAID

        # campi extra opzionali
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

        db.add(order)
        db.commit()
        db.refresh(order)

        log.info("Ordine marcato PAID/STRIPE. order_id=%s", order.id)

        # 1) Fulfillment licenza (se disponibile)
        _maybe_fulfill_license(order)

        # 2) Email “pagamento ricevuto” (se disponibile)
        _maybe_send_payment_email(order)

        return {"ok": True, "order_id": order.id, "status": "PAID"}

    # -----------------------------------
    # altri eventi: ignoriamo
    # -----------------------------------
    return {"ok": True, "ignored": event_type}
