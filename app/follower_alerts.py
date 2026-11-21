# app/follower_alerts.py
"""
Avvisi ai follower quando una guida pubblica un tour nuovo (2026-11-21).

Ogni CHECK_EVERY_SECONDS legge da Supabase i tour pubblicati per la prima
volta (books.first_published_at, scritto da un trigger) e non ancora gestiti
(followers_notified_at vuoto). Regole decise con Stefano:
  - si aspetta SETTLE_MINUTES dalla prima pubblicazione: se la guida ritira
    subito il tour per correggerlo, nessun avviso;
  - il tour deve essere davvero nel catalogo (vista public_tours: pubblicato
    e con almeno una tappa ascoltabile), altrimenti si riprova al giro dopo;
  - al massimo 1 avviso al giorno per guida: un secondo tour nelle 24 ore
    viene segnato come gestito senza avvisare;
  - solo i tour pubblicati per la PRIMA volta (le modifiche non avvisano).
Toccando la notifica l'app apre la pagina del tour (data.type = new_tour).

Variabile: FOLLOWER_ALERTS=0 per spegnere il giro.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import requests

from app.push import send_push_i18n
from routers.admin_licenses import _env

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 5 * 60
FIRST_RUN_DELAY_SECONDS = 90
SETTLE_MINUTES = 10
GIVE_UP_DAYS = 7  # un tour pubblicato ma mai ascoltabile non si controlla per sempre


def _sb():
    from routers.revenuecat_pro import _headers, _supabase

    base, key = _supabase()
    return base, key, _headers


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _texts(guide: str, title: str) -> dict[str, tuple[str, str]]:
    return {
        "it": (f"🐥 {guide} ha pubblicato un nuovo tour", f"«{title}»: la prima tappa è gratis, ascoltala ora."),
        "en": (f"🐥 {guide} published a new tour", f"“{title}”: the first stop is free, listen now."),
        "es": (f"🐥 {guide} ha publicado un tour nuevo", f"«{title}»: la primera parada es gratis, escúchala ahora."),
        "fr": (f"🐥 {guide} a publié un nouveau tour", f"« {title} » : la première étape est gratuite, écoutez-la."),
        "de": (f"🐥 {guide} hat eine neue Tour veröffentlicht", f"„{title}“: Die erste Station ist kostenlos – jetzt anhören."),
    }


def _mark(base: str, key: str, headers, book_id: str) -> None:
    r = requests.patch(
        f"{base}/rest/v1/books",
        params={"id": f"eq.{book_id}"},
        json={"followers_notified_at": _iso(datetime.now(timezone.utc))},
        headers=headers(key, {"Prefer": "return=minimal"}),
        timeout=10,
    )
    r.raise_for_status()


def run_once() -> dict:
    base, key, headers = _sb()
    now = datetime.now(timezone.utc)
    r = requests.get(
        f"{base}/rest/v1/books",
        params={
            "select": "id,title,guide_id,first_published_at",
            "is_published": "eq.true",
            "followers_notified_at": "is.null",
            "first_published_at": f"lt.{_iso(now - timedelta(minutes=SETTLE_MINUTES))}",
            "order": "first_published_at.asc",
            "limit": "50",
        },
        headers=headers(key),
        timeout=15,
    )
    r.raise_for_status()
    books = r.json() or []
    result = {"candidates": len(books), "announced": 0, "skipped": 0, "pushes": 0}
    for b in books:
        book_id, guide_id = b["id"], b.get("guide_id")
        try:
            if not guide_id:
                _mark(base, key, headers, book_id)
                continue
            # nel catalogo? (pubblicato e con una tappa ascoltabile)
            in_catalog = requests.get(
                f"{base}/rest/v1/public_tours",
                params={"select": "id,title,guide_name", "id": f"eq.{book_id}"},
                headers=headers(key),
                timeout=10,
            ).json() or []
            if not in_catalog:
                first = datetime.fromisoformat(str(b["first_published_at"]).replace("Z", "+00:00"))
                if now - first > timedelta(days=GIVE_UP_DAYS):
                    _mark(base, key, headers, book_id)
                continue
            # limite: 1 avviso al giorno per guida
            recent = requests.get(
                f"{base}/rest/v1/books",
                params={
                    "select": "id",
                    "guide_id": f"eq.{guide_id}",
                    "followers_notified_at": f"gt.{_iso(now - timedelta(hours=24))}",
                    "id": f"neq.{book_id}",
                    "limit": "1",
                },
                headers=headers(key),
                timeout=10,
            ).json() or []
            # Segniamo PRIMA di inviare: se qualcosa si rompe a metà, niente doppioni.
            _mark(base, key, headers, book_id)
            if recent:
                result["skipped"] += 1
                logger.info("Avvisi follower: tour %s saltato (già un avviso oggi per la guida)", book_id)
                continue
            followers = requests.get(
                f"{base}/rest/v1/guide_follows",
                params={"select": "follower_id", "guide_id": f"eq.{guide_id}"},
                headers=headers(key),
                timeout=10,
            ).json() or []
            tour = in_catalog[0]
            texts = _texts((tour.get("guide_name") or "").strip() or "VoiceGuide", (tour.get("title") or "").strip())
            for f in followers:
                result["pushes"] += send_push_i18n(f["follower_id"], texts, {"type": "new_tour", "tour_id": book_id})
            result["announced"] += 1
            logger.info("Avvisi follower: tour %s annunciato a %s follower", book_id, len(followers))
        except Exception as e:
            logger.error("Avvisi follower: tour %s non gestito: %s", book_id, e)
    return result


async def _loop() -> None:
    await asyncio.sleep(FIRST_RUN_DELAY_SECONDS)
    while True:
        try:
            res = await asyncio.to_thread(run_once)
            if res.get("candidates"):
                logger.info("Avvisi follower: %s", res)
        except Exception as e:
            logger.error("Avvisi follower: giro fallito: %s", e)
        await asyncio.sleep(CHECK_EVERY_SECONDS)


def start_follower_alerts_loop() -> None:
    if _env("FOLLOWER_ALERTS", "1") == "0":
        return
    asyncio.get_event_loop().create_task(_loop())
