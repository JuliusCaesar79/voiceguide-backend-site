# app/play_voided.py
"""
Rimborsi di Google Play letti direttamente da Google (piano B, 2026-11-21).

Perché: RevenueCat non riceve i rimborsi dei prodotti a pagamento singolo
(tour `tour_*`, licenze `live_*`): l'ordine di prova GPA.3366-1600-5017-90522,
rimborsato su Play Console il 19/11, dopo 2 giorni era ancora attivo.

Cosa fa: ogni CHECK_EVERY_SECONDS chiede alla Voided Purchases API di Google
gli acquisti annullati/rimborsati degli ultimi LOOKBACK_DAYS giorni (Google
ne conserva 30) e, per ciascun ordine (`orderId` = GPA.…):
  - tour a tappe: riga di public.tour_purchases → `refunded` (tour richiuso,
    l'app lo toglie anche dal telefono);
  - licenze live: licenza disattivata, ordine REFUNDED, blocco su AirLink.
Tutto è idempotente: rifarlo sugli stessi ordini non cambia niente.

Variabili d'ambiente:
  GOOGLE_PLAY_SERVICE_ACCOUNT_JSON  contenuto del file .json dell'account di
                                    servizio con accesso a Play Console
                                    (lo stesso di RevenueCat)
  GOOGLE_PLAY_PACKAGE_NAME          default com.voiceguideairlinkbare
  PLAY_VOIDED_SYNC                  "0" per spegnere il giro automatico

A mano (admin del sito): POST /api/admin/play/voided-sync
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from fastapi import APIRouter, Depends
from jose import jwt
from sqlalchemy.orm import Session

from app.db import SessionLocal
from models.licenses import License
from models.orders import Order, PaymentStatus
from routers.admin_licenses import _env
from routers.auth_admin import get_current_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/play", tags=["Admin - Rimborsi Google Play"])

CHECK_EVERY_SECONDS = 6 * 3600
FIRST_RUN_DELAY_SECONDS = 120
LOOKBACK_DAYS = 30
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
DEFAULT_PACKAGE = "com.voiceguideairlinkbare"


# ------------------------------------------------------------- Google ----

def _credentials() -> Optional[dict]:
    raw = _env("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except ValueError:
        logger.error("Rimborsi Play: GOOGLE_PLAY_SERVICE_ACCOUNT_JSON non è un JSON valido")
        return None
    if not info.get("client_email") or not info.get("private_key"):
        logger.error("Rimborsi Play: nel JSON mancano client_email/private_key")
        return None
    return info


def _access_token(info: dict) -> str:
    now = int(time.time())
    token_uri = info.get("token_uri") or "https://oauth2.googleapis.com/token"
    assertion = jwt.encode(
        {"iss": info["client_email"], "scope": SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600},
        info["private_key"],
        algorithm="RS256",
        headers={"kid": info.get("private_key_id")} if info.get("private_key_id") else None,
    )
    r = requests.post(
        token_uri,
        data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def fetch_voided(info: dict) -> list[dict[str, Any]]:
    package = _env("GOOGLE_PLAY_PACKAGE_NAME", DEFAULT_PACKAGE)
    token = _access_token(info)
    url = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package}/purchases/voidedpurchases"
    params: dict[str, Any] = {
        "startTime": str(int((time.time() - LOOKBACK_DAYS * 86400 + 600) * 1000)),
        "maxResults": "1000",
        "type": "0",  # solo acquisti singoli (gli abbonamenti Pro li gestisce già RevenueCat)
    }
    out: list[dict[str, Any]] = []
    for _ in range(20):
        r = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Google Voided Purchases API {r.status_code}: {r.text[:300]}")
        body = r.json() or {}
        out.extend(body.get("voidedPurchases") or [])
        nxt = (body.get("tokenPagination") or {}).get("nextPageToken")
        if not nxt:
            break
        params["token"] = nxt
    return out


# -------------------------------------------------------- applicazione ----

def _refund_tour(order_id: str, voided_at: str) -> int:
    from routers.revenuecat_pro import _headers, _supabase

    base, key = _supabase()
    r = requests.patch(
        f"{base}/rest/v1/tour_purchases",
        params={"transaction_id": f"eq.{order_id}", "status": "neq.refunded"},
        json={"status": "refunded", "refunded_at": voided_at},
        headers=_headers(key, {"Prefer": "return=representation"}),
        timeout=10,
    )
    r.raise_for_status()
    return len(r.json() or [])


def _refund_licenses(db: Session, order_id: str) -> list[str]:
    from routers.revenuecat_webhook import _airlink_block

    # note della licenza: revenuecat:<store>:<ambiente>:<orderId>
    licenses = db.query(License).filter(License.notes.like(f"revenuecat:PLAY_STORE:%:{order_id}")).all()
    changed = [l for l in licenses if l.is_active]
    if not changed:
        return []
    for lic in changed:
        lic.is_active = False
        db.add(lic)
    order_ids = {l.order_id for l in changed if l.order_id}
    for order in db.query(Order).filter(Order.id.in_(order_ids)).all():
        order.payment_status = PaymentStatus.REFUNDED
        db.add(order)
    db.commit()
    for lic in changed:
        _airlink_block(lic.code)
    return [l.code for l in changed]


def sync_voided() -> dict[str, Any]:
    info = _credentials()
    if not info:
        return {"ok": False, "status": "no_credentials"}
    voided = fetch_voided(info)
    tours, licenses = 0, []
    db = SessionLocal()
    try:
        for v in voided:
            order_id = (v.get("orderId") or "").strip()
            if not order_id:
                continue
            ms = int(v.get("voidedTimeMillis") or 0)
            voided_at = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat() if ms else datetime.now(timezone.utc).isoformat()
            try:
                n = _refund_tour(order_id, voided_at)
                if n:
                    logger.info("Rimborsi Play: tour richiuso per l'ordine %s", order_id)
                tours += n
                codes = _refund_licenses(db, order_id)
                if codes:
                    logger.info("Rimborsi Play: licenze disattivate per l'ordine %s: %s", order_id, codes)
                licenses += codes
            except Exception as e:
                db.rollback()
                logger.error("Rimborsi Play: ordine %s non aggiornato: %s", order_id, e)
    finally:
        db.close()
    result = {"ok": True, "voided": len(voided), "tours_refunded": tours, "licenses_refunded": licenses}
    logger.info("Rimborsi Play: %s", result)
    return result


async def _loop() -> None:
    await asyncio.sleep(FIRST_RUN_DELAY_SECONDS)
    while True:
        try:
            await asyncio.to_thread(sync_voided)
        except Exception as e:
            logger.error("Rimborsi Play: giro fallito: %s", e)
        await asyncio.sleep(CHECK_EVERY_SECONDS)


def start_voided_loop() -> None:
    if _env("PLAY_VOIDED_SYNC", "1") == "0":
        return
    asyncio.get_event_loop().create_task(_loop())


@router.post("/voided-sync")
def voided_sync_now(_admin=Depends(get_current_admin)):
    return sync_voided()
