# routers/app_tour_purchases.py
"""
Acquisto dei tour a tappe dentro l'app (catalogo, tappa 2 — 2026-11-19).

Il turista compra un tour pagando il prodotto della sua FASCIA di prezzo
(`tour_299` … `tour_1499`, Google Play / App Store via RevenueCat). Il
prodotto dello store non dice quale tour: per questo, prima di pagare, l'app
apre una "richiesta" qui, e dopo il pagamento la richiesta diventa l'acquisto.

  POST /api/app/tours/{book_id}/purchase-intent   (Bearer token Supabase)
      Controlla che il tour sia in vendita e non sia già suo; registra la
      richiesta (riga `pending` in public.tour_purchases, una sola per utente)
      e risponde con il prodotto da comprare.
  POST /api/app/tours/claim                        (Bearer token Supabase)
      Subito dopo il pagamento: chiede a RevenueCat (chiave segreta
      REVENUECAT_SECRET_KEY) le transazioni `tour_*` dell'utente e conferma la
      richiesta. Senza chiave risponde "waiting": basta il webhook.
  Webhook RevenueCat (routers/revenuecat_webhook.py) → handle_tour_event:
      stesso abbinamento con i dati dell'evento (arriva con qualche minuto di
      ritardo, fa da rete di sicurezza); rimborso → `refunded`, tour richiuso.

Tutto è idempotente sull'id della transazione dello store (colonna unica).
Una transazione senza richiesta compatibile diventa `unmatched` (assistenza).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests
from fastapi import APIRouter, Header, HTTPException

from routers.admin_licenses import _env
from routers.app_licenses import DEFAULT_SUPABASE_ANON_KEY
from routers.revenuecat_pro import DEFAULT_SUPABASE_URL, UUID_RE, _headers, _supabase

router = APIRouter(prefix="/api/app/tours", tags=["App - Acquisto tour"])
logger = logging.getLogger(__name__)

TOUR_PRODUCT = re.compile(r"^(tour_(\d+))(?::.*)?$")
# Una richiesta vale per un pagamento fatto entro questo tempo.
INTENT_MAX_AGE = timedelta(hours=2)
CLOCK_SLACK = timedelta(minutes=2)
# Chi ha già avuto questo numero di rimborsi di tour non può più comprarne
# dall'app (deciso da Stefano il 2026-11-19).
MAX_REFUNDS = 2


def tour_product(product_id: Optional[str]) -> Optional[str]:
    m = TOUR_PRODUCT.match((product_id or "").strip().lower())
    return m.group(1) if m else None


# ---------------------------------------------------------------- utilità ----

def _user_id(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    base = _env("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")
    key = _env("SUPABASE_ANON_KEY", DEFAULT_SUPABASE_ANON_KEY)
    try:
        r = requests.get(f"{base}/auth/v1/user", headers={"apikey": key, "Authorization": f"Bearer {token}"}, timeout=10)
    except Exception as e:
        logger.warning("tour purchase: Supabase non raggiungibile: %s", e)
        raise HTTPException(status_code=503, detail="Auth unavailable")
    if r.status_code != 200:
        logger.warning("tour purchase: token rifiutato (%s)", r.status_code)
        raise HTTPException(status_code=401, detail="Invalid token")
    uid = str((r.json() or {}).get("id") or "")
    if not UUID_RE.match(uid):
        raise HTTPException(status_code=401, detail="Invalid token")
    return uid.lower()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _tier_cents(product: str) -> Optional[int]:
    m = TOUR_PRODUCT.match(product)
    return int(m.group(2)) if m else None


def _rows(base: str, key: str, params: dict) -> list[dict]:
    r = requests.get(f"{base}/rest/v1/tour_purchases", params=params, headers=_headers(key), timeout=10)
    r.raise_for_status()
    return r.json() or []


# ------------------------------------------------------------ conferma ----

def confirm_transaction(
    user_id: str,
    product: str,
    tx: str,
    *,
    store: Optional[str],
    environment: Optional[str],
    purchased_at: Optional[datetime],
    price_cents: Optional[int] = None,
    currency: Optional[str] = None,
) -> str:
    """Abbina una transazione `tour_*` alla richiesta dell'utente. Idempotente.
    Risponde: "exists", "active" o "unmatched"."""
    base, key = _supabase()
    purchased_at = purchased_at or _now()

    existing = _rows(base, key, {"transaction_id": f"eq.{tx}", "select": "id,status,price_cents"})
    if existing:
        if price_cents is not None and existing[0].get("status") == "active":
            # Il webhook porta il prezzo vero (valuta dello store): aggiorna.
            requests.patch(
                f"{base}/rest/v1/tour_purchases",
                params={"id": f"eq.{existing[0]['id']}"},
                json={"price_cents": price_cents, "currency": (currency or "EUR")[:3]},
                headers=_headers(key, {"Prefer": "return=minimal"}),
                timeout=10,
            )
        return "exists"

    pending = _rows(base, key, {
        "user_id": f"eq.{user_id}",
        "product_id": f"eq.{product}",
        "status": "eq.pending",
        "select": "id,created_at,book_id",
        "order": "created_at.desc",
        "limit": "1",
    })
    if pending:
        created = _parse_ts(pending[0].get("created_at"))
        if created and purchased_at - INTENT_MAX_AGE <= created <= purchased_at + CLOCK_SLACK:
            r = requests.patch(
                f"{base}/rest/v1/tour_purchases",
                params={"id": f"eq.{pending[0]['id']}", "status": "eq.pending"},
                json={
                    "status": "active",
                    "transaction_id": tx,
                    "store": store,
                    "environment": environment,
                    "purchased_at": purchased_at.isoformat(),
                    "price_cents": price_cents if price_cents is not None else _tier_cents(product),
                    "currency": (currency or "EUR")[:3],
                },
                headers=_headers(key, {"Prefer": "return=representation"}),
                timeout=10,
            )
            if r.status_code == 409:
                return "exists"  # l'altra strada (app o webhook) è arrivata prima
            r.raise_for_status()
            rows = r.json()
            if rows:
                logger.info("Tour: acquisto %s confermato per %s (tour %s, %s)", tx, user_id, pending[0].get("book_id"), product)
                # Notifica alla guida: "Hai venduto un tour!" (non blocca mai)
                try:
                    from app.push import push_tour_sold

                    push_tour_sold(rows[0])
                except Exception as e:
                    logger.warning("Tour: avviso di vendita non inviato: %s", e)
                return "active"
            # richiesta presa nel frattempo dall'altra strada: ricontrolla
            if _rows(base, key, {"transaction_id": f"eq.{tx}", "select": "id"}):
                return "exists"

    # Pagamento senza richiesta compatibile: lo annotiamo per l'assistenza.
    r = requests.post(
        f"{base}/rest/v1/tour_purchases",
        params={"on_conflict": "transaction_id"},
        json={
            "user_id": user_id,
            "product_id": product,
            "status": "unmatched",
            "transaction_id": tx,
            "store": store,
            "environment": environment,
            "purchased_at": purchased_at.isoformat(),
            "price_cents": price_cents if price_cents is not None else _tier_cents(product),
            "currency": (currency or "EUR")[:3],
        },
        headers=_headers(key, {"Prefer": "resolution=ignore-duplicates,return=minimal"}),
        timeout=10,
    )
    r.raise_for_status()
    logger.error("Tour: transazione %s (%s) di %s senza richiesta: annotata come unmatched", tx, product, user_id)
    return "unmatched"


def _revenuecat_tour_transactions(user_id: str) -> Optional[list[dict]]:
    """Transazioni `tour_*` dell'utente secondo RevenueCat; None se manca la chiave."""
    secret = _env("REVENUECAT_SECRET_KEY")
    if not secret:
        return None
    r = requests.get(
        f"https://api.revenuecat.com/v1/subscribers/{user_id}",
        headers={"Authorization": f"Bearer {secret}"},
        timeout=10,
    )
    r.raise_for_status()
    non_subs = ((r.json() or {}).get("subscriber") or {}).get("non_subscriptions") or {}
    out = []
    for product_id, items in non_subs.items():
        product = tour_product(product_id)
        if not product:
            continue
        for it in items or []:
            tx = it.get("store_transaction_id") or it.get("id")
            if tx:
                out.append({
                    "product": product,
                    "tx": str(tx),
                    "store": str(it.get("store") or "").upper() or None,
                    "environment": "SANDBOX" if it.get("is_sandbox") else "PRODUCTION",
                    "purchased_at": _parse_ts(it.get("purchase_date")),
                })
    return out


# ------------------------------------------------------------ webhook ----

def handle_tour_event(event: dict[str, Any], refund: bool) -> dict:
    product = tour_product(event.get("product_id"))
    tx = event.get("transaction_id") or event.get("original_transaction_id")
    user_id = next(
        (str(c).lower() for c in [event.get("app_user_id"), event.get("original_app_user_id"), *(event.get("aliases") or [])]
         if c and UUID_RE.match(str(c))),
        None,
    )
    if not product or not tx or not user_id:
        logger.error("Tour: evento %s incompleto (%s, %s, %s)", event.get("type"), product, tx, event.get("app_user_id"))
        return {"ok": True, "status": "ignored"}
    base, key = _supabase()
    try:
        if refund:
            r = requests.patch(
                f"{base}/rest/v1/tour_purchases",
                params={"transaction_id": f"eq.{tx}"},
                json={"status": "refunded", "refunded_at": _now().isoformat()},
                headers=_headers(key, {"Prefer": "return=representation"}),
                timeout=10,
            )
            r.raise_for_status()
            logger.info("Tour: rimborso %s, righe richiuse: %s", tx, len(r.json() or []))
            return {"ok": True, "status": "refunded"}
        price = event.get("price_in_purchased_currency")
        try:
            cents = int(round(float(price) * 100)) if price is not None else None
        except (TypeError, ValueError):
            cents = None
        status = confirm_transaction(
            user_id, product, str(tx),
            store=event.get("store"),
            environment=event.get("environment") or "PRODUCTION",
            purchased_at=_parse_ts(event.get("purchased_at_ms")),
            price_cents=cents,
            currency=event.get("currency"),
        )
        return {"ok": True, "status": status}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Tour: Supabase non raggiungibile per %s", tx)
        raise HTTPException(status_code=502, detail="Supabase unavailable")  # RevenueCat ritenta


# ------------------------------------------------------------- endpoint ----

@router.post("/{book_id}/purchase-intent")
def purchase_intent(book_id: str, source: str = "app", authorization: Optional[str] = Header(default=None)):
    # source=guide_link: il turista è arrivato dal link di vendita della guida
    # (tappa 4): la quota della guida sale a 80/90% (calcolata da Supabase).
    source = "guide_link" if source == "guide_link" else "app"
    user_id = _user_id(authorization)
    if not UUID_RE.match(book_id):
        raise HTTPException(status_code=404, detail="not_found")
    base, key = _supabase()
    r = requests.get(
        f"{base}/rest/v1/books",
        params={"id": f"eq.{book_id}", "select": "id,title,guide_id,price_tier,is_published"},
        headers=_headers(key),
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json() or []
    if not rows or not rows[0].get("is_published"):
        raise HTTPException(status_code=404, detail="not_found")
    book = rows[0]
    product = tour_product(book.get("price_tier"))
    if not product:
        raise HTTPException(status_code=409, detail="not_for_sale")
    if str(book.get("guide_id")).lower() == user_id:
        raise HTTPException(status_code=409, detail="own_tour")

    if _rows(base, key, {"user_id": f"eq.{user_id}", "book_id": f"eq.{book_id}", "status": "eq.active", "select": "id"}):
        return {"status": "owned"}

    refunds = _rows(base, key, {"user_id": f"eq.{user_id}", "status": "eq.refunded", "select": "id", "limit": str(MAX_REFUNDS)})
    if len(refunds) >= MAX_REFUNDS:
        logger.warning("Tour: acquisto rifiutato a %s (%s rimborsi)", user_id, len(refunds))
        raise HTTPException(status_code=403, detail="too_many_refunds")

    # Una sola richiesta aperta per utente: così il pagamento si abbina senza dubbi.
    requests.delete(
        f"{base}/rest/v1/tour_purchases",
        params={"user_id": f"eq.{user_id}", "status": "eq.pending"},
        headers=_headers(key, {"Prefer": "return=minimal"}),
        timeout=10,
    ).raise_for_status()
    requests.post(
        f"{base}/rest/v1/tour_purchases",
        json={
            "user_id": user_id,
            "book_id": book_id,
            "guide_id": book.get("guide_id"),
            "book_title": book.get("title") or "",
            "product_id": product,
            "status": "pending",
            "source": source,
        },
        headers=_headers(key, {"Prefer": "return=minimal"}),
        timeout=10,
    ).raise_for_status()
    logger.info("Tour: richiesta di %s per il tour %s (%s, %s)", user_id, book_id, product, source)
    return {"status": "ready", "product_id": product}


@router.post("/claim")
def claim(authorization: Optional[str] = Header(default=None)):
    user_id = _user_id(authorization)
    try:
        txs = _revenuecat_tour_transactions(user_id)
    except Exception as e:
        logger.warning("Tour: RevenueCat non raggiungibile per %s: %s", user_id, e)
        txs = None
    if txs is None:
        return {"status": "waiting"}
    results = [
        confirm_transaction(
            user_id, t["product"], t["tx"],
            store=t["store"], environment=t["environment"], purchased_at=t["purchased_at"],
        )
        for t in txs
    ]
    return {"status": "done", "confirmed": results.count("active")}
