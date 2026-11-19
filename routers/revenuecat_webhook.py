# routers/revenuecat_webhook.py
"""
Acquisti dentro l'app (Google Play, poi App Store) tramite RevenueCat.
Fase 2, punto 5 (2026-11-18).

POST /api/webhooks/revenuecat
  Header: Authorization: <REVENUECAT_WEBHOOK_SECRET>  (lo stesso valore
  impostato nella dashboard di RevenueCat, Integrations > Webhooks)

Cosa fa:
  - licenze live (`live_5` ... `live_100`, acquisti singoli): crea un ordine
    PAID e la licenza, esattamente come un acquisto sul sito. La licenza è
    legata all'email dell'account (attributo `$email` che l'app imposta su
    RevenueCat), quindi compare subito in "Le mie licenze".
  - rimborso di una licenza (CANCELLATION / REFUND): ordine REFUNDED e
    licenza disattivata; da "Le mie licenze" sparisce.
  - licenze `live_N_pro`: le stesse, prezzo Pro (-20%), vendute solo alle
    guide Pro;
  - abbonamento Pro: `routers/revenuecat_pro.py` (Supabase, premium_until);
  - tour a tappe: per ora solo registrati nei log.

Idempotente: RevenueCat può mandare lo stesso evento più volte. La chiave è
l'id della transazione dello store, salvato nelle note della licenza
(`revenuecat:<store>:<ambiente>:<transaction_id>`).
"""
from __future__ import annotations

import hmac
import logging
import re
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.fulfillment_service import fulfill_paid_order
from models.licenses import License
from models.orders import Order, OrderType, PaymentMethod, PaymentStatus
from models.packages import Package
from routers.admin_licenses import _env
from routers.checkout import _resolve_single_package_id
from routers.revenuecat_pro import handle_pro_event, is_pro_event

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)

# `live_5` … `live_100` e le stesse con lo sconto Pro (-20%): `live_5_pro` …
LIVE_PRODUCT = re.compile(r"^live_(\d+)(_pro)?$")
PRO_DISCOUNT = Decimal("0.80")
PURCHASE_EVENTS = {"NON_RENEWING_PURCHASE", "INITIAL_PURCHASE"}
REFUND_EVENTS = {"CANCELLATION", "REFUND"}
SUPPORTED_LANGS = {"it", "en", "fr", "es", "de"}


def _check_auth(authorization: Optional[str]) -> None:
    secret = (_env("REVENUECAT_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise HTTPException(status_code=500, detail="RevenueCat webhook not configured")
    got = (authorization or "").strip()
    if got.lower().startswith("bearer "):
        got = got[7:].strip()
    if not hmac.compare_digest(got.encode(), secret.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _attr(event: dict[str, Any], name: str) -> Optional[str]:
    attrs = event.get("subscriber_attributes") or {}
    item = attrs.get(name) or {}
    value = item.get("value") if isinstance(item, dict) else None
    return str(value).strip() if value else None


def _tx_key(event: dict[str, Any]) -> Optional[str]:
    tx = event.get("transaction_id") or event.get("original_transaction_id")
    if not tx:
        return None
    store = event.get("store") or "UNKNOWN_STORE"
    env = event.get("environment") or "PRODUCTION"
    return f"revenuecat:{store}:{env}:{tx}"


def _find_licenses(db: Session, key: str) -> list[License]:
    return db.query(License).filter(License.notes == key).all()


def _handle_live_purchase(db: Session, event: dict[str, Any], max_guests: int, pro_price: bool = False) -> dict:
    key = _tx_key(event)
    if not key:
        raise HTTPException(status_code=400, detail="Missing transaction_id")

    existing = _find_licenses(db, key)
    if existing:
        return {"ok": True, "status": "already_fulfilled", "licenses": [l.code for l in existing]}

    email = (_attr(event, "$email") or "").lower()
    if not email or "@" not in email:
        # Senza email la licenza non arriverebbe in "Le mie licenze": meglio
        # farlo riprovare (RevenueCat ritenta) e vederlo nei log.
        logger.error("RevenueCat: acquisto %s senza $email (utente %s)", key, event.get("app_user_id"))
        raise HTTPException(status_code=422, detail="Missing $email subscriber attribute")

    lang = (_attr(event, "language") or "it").lower()[:2]
    if lang not in SUPPORTED_LANGS:
        lang = "en"

    package_id = _resolve_single_package_id(db, max_guests=max_guests)
    pkg = db.query(Package).filter(Package.id == package_id).first()
    price = Decimal(str(pkg.price)) if pkg and pkg.price is not None else Decimal("0")
    if pro_price:
        price = (price * PRO_DISCOUNT).quantize(Decimal("0.01"))

    order = Order(
        buyer_email=email,
        order_type=OrderType.SINGLE,
        package_id=package_id,
        quantity=1,
        subtotal_amount=price,
        discount_amount=Decimal("0"),
        total_amount=price,
        payment_method=PaymentMethod.OTHER,  # acquisto in app (store)
        payment_status=PaymentStatus.PAID,
        language=lang,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    try:
        result = fulfill_paid_order(db=db, order=order, license_notes=key, issued_to_email=email)
    except Exception:
        logger.exception("RevenueCat: fulfillment fallito per %s (ordine %s)", key, order.id)
        db.rollback()
        order.payment_status = PaymentStatus.FAILED
        db.add(order)
        db.commit()
        raise HTTPException(status_code=500, detail="Fulfillment failed")

    logger.info("RevenueCat: licenza live_%s per %s, ordine %s, %s", max_guests, email, order.id, key)
    return result


def _handle_refund(db: Session, event: dict[str, Any]) -> dict:
    key = _tx_key(event)
    if not key:
        return {"ok": True, "status": "ignored"}
    licenses = _find_licenses(db, key)
    if not licenses:
        return {"ok": True, "status": "no_license"}
    order_ids = {l.order_id for l in licenses if l.order_id}
    for lic in licenses:
        lic.is_active = False
        db.add(lic)
    for order in db.query(Order).filter(Order.id.in_(order_ids)).all():
        order.payment_status = PaymentStatus.REFUNDED
        db.add(order)
    db.commit()
    logger.info("RevenueCat: rimborso %s, licenze disattivate: %s", key, [l.code for l in licenses])
    return {"ok": True, "status": "refunded", "licenses": [l.code for l in licenses]}


@router.post("/revenuecat")
async def revenuecat_webhook(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _check_auth(authorization)
    body = await request.json()
    event = (body or {}).get("event") or {}
    etype = event.get("type")
    product = event.get("product_id") or ""

    if etype == "TEST":
        return {"ok": True, "status": "test"}

    if is_pro_event(event):
        return handle_pro_event(event)

    m = LIVE_PRODUCT.match(product)
    if m and etype in PURCHASE_EVENTS:
        return _handle_live_purchase(db, event, int(m.group(1)), pro_price=bool(m.group(2)))

    if m and etype in REFUND_EVENTS:
        # Per un acquisto singolo (non un abbonamento) CANCELLATION vuol dire
        # che il pagamento è stato rimborsato.
        return _handle_refund(db, event)

    logger.info("RevenueCat: evento %s per %s (non ancora gestito)", etype, product)
    return {"ok": True, "status": "ignored"}
