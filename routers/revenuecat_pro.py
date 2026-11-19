# routers/revenuecat_pro.py
"""
Guida Pro comprata in app (abbonamento `pro`, piani `mensile`/`annuale`,
prova di 14 giorni gestita da Google/Apple). Fase 2, punto 5 (2026-11-19).

Il Pro vive su Supabase (progetto `itinerarium`) nella colonna
`guides.premium_until`: è lo stesso "premium" di Itinerarium (decisione di
Stefano: un solo Pro), scritto anche da Lemon Squeezy e dai regali dell'admin.
Qui si aggiorna con la chiave di servizio di Supabase (variabile
SUPABASE_SERVICE_ROLE_KEY su Railway).

Regole:
  - acquisto, rinnovo, ripresa, cambio piano: premium_until = la data più
    lontana tra quella attuale e la scadenza dello store (così un mese
    regalato non si perde);
  - disdetta normale: niente, il Pro resta fino alla fine del periodo pagato
    e poi scade da solo;
  - rimborso (CANCELLATION con motivo CUSTOMER_SUPPORT): premium_until
    riportato alla scadenza indicata dallo store, se è prima.
Ogni evento viene anche annotato in `public.purchases` (provider
`revenuecat`), per i conti e la futura dashboard admin.

L'utente RevenueCat è l'utente Supabase (stesso id): lo imposta l'app.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests
from fastapi import HTTPException

from routers.admin_licenses import _env

logger = logging.getLogger(__name__)

DEFAULT_SUPABASE_URL = "https://dtbcfjsqwhmdfwkxighr.supabase.co"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

GRACE = timedelta(days=1)

GRANT_EVENTS = {
    "INITIAL_PURCHASE",
    "RENEWAL",
    "UNCANCELLATION",
    "PRODUCT_CHANGE",
    "SUBSCRIPTION_EXTENDED",
    "TEMPORARY_ENTITLEMENT_GRANT",
}


def is_pro_event(event: dict[str, Any]) -> bool:
    product = (event.get("product_id") or "").lower()
    entitlements = [str(e).lower() for e in (event.get("entitlement_ids") or [])]
    return product == "pro" or product.startswith("pro:") or "pro" in entitlements


def _supabase() -> tuple[str, str]:
    key = _env("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        logger.error("RevenueCat Pro: manca SUPABASE_SERVICE_ROLE_KEY")
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return _env("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/"), key


def _headers(key: str, extra: Optional[dict] = None) -> dict:
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def _user_id(event: dict[str, Any]) -> Optional[str]:
    candidates = [event.get("app_user_id"), event.get("original_app_user_id"), *(event.get("aliases") or [])]
    for c in candidates:
        if c and UUID_RE.match(str(c)):
            return str(c).lower()
    return None


def _ms_to_dt(ms: Any) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _current_until(base: str, key: str, user_id: str) -> tuple[bool, Optional[datetime]]:
    r = requests.get(
        f"{base}/rest/v1/guides",
        params={"id": f"eq.{user_id}", "select": "premium_until"},
        headers=_headers(key),
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json() or []
    if not rows:
        return False, None
    return True, _parse_ts(rows[0].get("premium_until"))


def _set_until(base: str, key: str, user_id: str, until: datetime) -> None:
    r = requests.patch(
        f"{base}/rest/v1/guides",
        params={"id": f"eq.{user_id}"},
        json={"premium_until": until.isoformat()},
        headers=_headers(key, {"Prefer": "return=minimal"}),
        timeout=10,
    )
    r.raise_for_status()


def _record(base: str, key: str, user_id: str, event: dict[str, Any], status: str) -> None:
    """Annota l'evento in public.purchases (una riga per evento, mai doppia)."""
    event_id = event.get("id") or f"{event.get('type')}:{event.get('transaction_id')}"
    price = event.get("price_in_purchased_currency")
    try:
        amount_cents = int(round(float(price) * 100)) if price is not None else 0
    except (TypeError, ValueError):
        amount_cents = 0
    row = {
        "guide_id": user_id,
        "provider": "revenuecat",
        "provider_order_id": f"{event.get('environment') or 'PRODUCTION'}:{event_id}",
        "status": status,
        "amount_cents": max(amount_cents, 0),
        "currency": (event.get("currency") or "EUR")[:3],
        "raw_payload": event,
    }
    try:
        r = requests.post(
            f"{base}/rest/v1/purchases",
            params={"on_conflict": "provider,provider_order_id"},
            json=row,
            headers=_headers(key, {"Prefer": "resolution=ignore-duplicates,return=minimal"}),
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:  # la registrazione non deve far fallire il Pro
        logger.warning("RevenueCat Pro: registrazione acquisto non riuscita: %s", e)


def handle_pro_event(event: dict[str, Any]) -> dict:
    etype = event.get("type")
    user_id = _user_id(event)
    if not user_id:
        logger.error("RevenueCat Pro: evento %s senza utente Supabase (%s)", etype, event.get("app_user_id"))
        return {"ok": True, "status": "no_user"}

    store_until = _ms_to_dt(event.get("expiration_at_ms"))
    refund = etype == "CANCELLATION" and event.get("cancel_reason") == "CUSTOMER_SUPPORT"
    if etype not in GRANT_EVENTS and not refund:
        logger.info("RevenueCat Pro: %s per %s (nessuna modifica)", etype, user_id)
        return {"ok": True, "status": "noted"}
    if not store_until:
        logger.error("RevenueCat Pro: %s senza expiration_at_ms per %s", etype, user_id)
        return {"ok": True, "status": "no_expiration"}

    base, key = _supabase()
    try:
        exists, current = _current_until(base, key, user_id)
        if not exists:
            logger.error("RevenueCat Pro: profilo %s non trovato", user_id)
            return {"ok": True, "status": "no_profile"}
        if refund:
            new_until = min(current, store_until) if current else store_until
        else:
            # Gli avvisi di RevenueCat arrivano con qualche minuto di ritardo:
            # per i pagamenti veri 1 giorno di margine, così il giorno del
            # rinnovo la guida non risulta "non Pro" finché l'avviso non arriva.
            # Nelle prove (SANDBOX) niente margine, per vedere la scadenza vera.
            if (event.get("environment") or "PRODUCTION") == "PRODUCTION":
                store_until = store_until + GRACE
            new_until = max(current, store_until) if current else store_until
        if new_until != current:
            _set_until(base, key, user_id, new_until)
    except HTTPException:
        raise
    except Exception:
        # RevenueCat ritenta se rispondiamo con un errore.
        logger.exception("RevenueCat Pro: Supabase non raggiungibile per %s", user_id)
        raise HTTPException(status_code=502, detail="Supabase unavailable")

    _record(base, key, user_id, event, "refunded" if refund else (etype or "").lower())
    logger.info("RevenueCat Pro: %s per %s, Pro fino al %s", etype, user_id, new_until.isoformat())
    return {"ok": True, "status": "pro_updated", "premium_until": new_until.isoformat()}
