# app/push.py
"""
Notifiche push verso l'app (Firebase Cloud Messaging, API HTTP v1), 2026-11-21.

I telefoni si registrano dall'app (Supabase, tabella public.push_tokens via
register_push_token). Qui si leggono i token di un utente con la chiave
service role e si manda la notifica a ciascuno; i token che Google dice non
più validi (app disinstallata, dati cancellati) vengono tolti.

Testi: send_push_i18n riceve i testi nelle 5 lingue e usa la lingua salvata
con il token (quella dell'app sul telefono), con l'inglese di riserva.

Variabile d'ambiente:
  FIREBASE_SERVICE_ACCOUNT_JSON  contenuto del file .json "Account di servizio"
                                 di Firebase (firebase-adminsdk-…)
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Optional

import requests
from jose import jwt

from routers.admin_licenses import _env

logger = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_token_cache: dict[str, Any] = {"value": None, "exp": 0.0}
_lock = threading.Lock()


def _credentials() -> Optional[dict]:
    raw = _env("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except ValueError:
        logger.error("Push: FIREBASE_SERVICE_ACCOUNT_JSON non è un JSON valido")
        return None
    return info if info.get("client_email") and info.get("private_key") else None


def _access_token(info: dict) -> str:
    with _lock:
        if _token_cache["value"] and _token_cache["exp"] > time.time() + 60:
            return _token_cache["value"]
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
        body = r.json()
        _token_cache["value"] = body["access_token"]
        _token_cache["exp"] = time.time() + int(body.get("expires_in", 3600))
        return _token_cache["value"]


def _tokens_for(user_id: str) -> list[dict]:
    from routers.revenuecat_pro import _headers, _supabase

    base, key = _supabase()
    r = requests.get(
        f"{base}/rest/v1/push_tokens",
        params={"user_id": f"eq.{user_id}", "select": "token,lang,platform"},
        headers=_headers(key),
        timeout=10,
    )
    r.raise_for_status()
    return r.json() or []


def _drop_token(token: str) -> None:
    from routers.revenuecat_pro import _headers, _supabase

    base, key = _supabase()
    try:
        requests.delete(f"{base}/rest/v1/push_tokens", params={"token": f"eq.{token}"}, headers=_headers(key), timeout=10)
    except Exception as e:
        logger.warning("Push: token non rimosso: %s", e)


def _send_one(info: dict, token: str, title: str, body: str, data: Optional[dict]) -> bool:
    url = f"https://fcm.googleapis.com/v1/projects/{info['project_id']}/messages:send"
    message: dict[str, Any] = {
        "token": token,
        "notification": {"title": title, "body": body},
        "android": {"priority": "high", "notification": {"channel_id": "vg_avvisi"}},
        "apns": {"payload": {"aps": {"sound": "default"}}},
    }
    if data:
        message["data"] = {str(k): str(v) for k, v in data.items()}
    r = requests.post(
        url,
        json={"message": message},
        headers={"Authorization": f"Bearer {_access_token(info)}"},
        timeout=15,
    )
    if r.status_code == 200:
        return True
    text = r.text[:300]
    if r.status_code == 404 or "UNREGISTERED" in text or ("INVALID_ARGUMENT" in text and "registration token" in text.lower()):
        _drop_token(token)
        logger.info("Push: token scaduto rimosso")
    else:
        logger.warning("Push: invio fallito %s: %s", r.status_code, text)
    return False


def send_push_i18n(user_id: str, texts: dict[str, tuple[str, str]], data: Optional[dict] = None) -> int:
    """texts = {"it": (titolo, testo), "en": (...), ...}. Ritorna quante notifiche sono partite.
    Non solleva mai: una notifica non deve far fallire l'operazione che la manda."""
    info = _credentials()
    if not info:
        logger.info("Push: FIREBASE_SERVICE_ACCOUNT_JSON mancante, niente notifica")
        return 0
    try:
        sent = 0
        for row in _tokens_for(user_id):
            lang = (row.get("lang") or "en")[:2]
            title, body = texts.get(lang) or texts.get("en") or next(iter(texts.values()))
            if _send_one(info, row["token"], title, body, data):
                sent += 1
        return sent
    except Exception as e:
        logger.error("Push: invio a %s non riuscito: %s", user_id, e)
        return 0


def send_push_i18n_async(user_id: str, texts: dict[str, tuple[str, str]], data: Optional[dict] = None) -> None:
    """Come send_push_i18n ma in un thread: non rallenta webhook e risposte."""
    threading.Thread(target=send_push_i18n, args=(user_id, texts, data), daemon=True).start()


# ------------------------------------------------------- utenti ed eventi ----

def user_id_by_email(email: str) -> Optional[str]:
    """Account Supabase (app) con questa email, se esiste."""
    from routers.revenuecat_pro import _headers, _supabase

    email = (email or "").strip().lower()
    if "@" not in email:
        return None
    base, key = _supabase()
    r = requests.get(
        f"{base}/auth/v1/admin/users",
        params={"filter": email, "per_page": "50"},
        headers=_headers(key),
        timeout=10,
    )
    r.raise_for_status()
    for u in (r.json() or {}).get("users") or []:
        if (u.get("email") or "").lower() == email:
            return u.get("id")
    return None


def _license_ready_texts(count: int, max_guests: int) -> dict[str, tuple[str, str]]:
    if count <= 1:
        return {
            "it": ("🎟️ La tua licenza è pronta", f"Licenza per {max_guests} ospiti in «Le mie licenze». Buon tour!"),
            "en": ("🎟️ Your licence is ready", f"Licence for {max_guests} guests in “My licences”. Enjoy your tour!"),
            "es": ("🎟️ Tu licencia está lista", f"Licencia para {max_guests} invitados en «Mis licencias». ¡Buen tour!"),
            "fr": ("🎟️ Votre licence est prête", f"Licence pour {max_guests} invités dans « Mes licences ». Bonne visite !"),
            "de": ("🎟️ Deine Lizenz ist bereit", f"Lizenz für {max_guests} Gäste unter „Meine Lizenzen“. Viel Spaß bei der Tour!"),
        }
    return {
        "it": ("🎟️ Le tue licenze sono pronte", f"{count} licenze per {max_guests} ospiti in «Le mie licenze». Buoni tour!"),
        "en": ("🎟️ Your licences are ready", f"{count} licences for {max_guests} guests in “My licences”. Enjoy your tours!"),
        "es": ("🎟️ Tus licencias están listas", f"{count} licencias para {max_guests} invitados en «Mis licencias». ¡Buenos tours!"),
        "fr": ("🎟️ Vos licences sont prêtes", f"{count} licences pour {max_guests} invités dans « Mes licences ». Bonnes visites !"),
        "de": ("🎟️ Deine Lizenzen sind bereit", f"{count} Lizenzen für {max_guests} Gäste unter „Meine Lizenzen“. Viel Spaß bei den Touren!"),
    }


def push_license_ready(email: Optional[str], count: int, max_guests: int) -> None:
    """Avviso "licenza pronta" (acquisti in app e sul sito). In un thread, non blocca mai."""
    if not email or count <= 0:
        return

    def run():
        try:
            uid = user_id_by_email(email)
            if not uid:
                return  # comprata sul sito da chi non ha (ancora) l'app
            n = send_push_i18n(uid, _license_ready_texts(count, max_guests), {"type": "license_ready"})
            logger.info("Push: licenza pronta, notifiche inviate: %s", n)
        except Exception as e:
            logger.warning("Push: avviso licenza non inviato: %s", e)

    threading.Thread(target=run, daemon=True).start()


def _euro(cents: int, lang: str) -> str:
    s = f"{cents / 100:.2f}"
    return s if lang == "en" else s.replace(".", ",")


def push_tour_sold(row: dict) -> None:
    """Avviso alla guida a ogni tour venduto (riga di tour_purchases appena attivata)."""
    guide_id = row.get("guide_id")
    if not guide_id or guide_id == row.get("user_id"):
        return
    title_tour = (row.get("book_title") or "").strip() or "…"
    share = int(row.get("guide_share_cents") or 0)
    from_link = row.get("source") == "guide_link"

    def body(lang: str) -> str:
        e = _euro(share, lang)
        link = {
            "it": " (dal tuo link)", "en": " (from your link)", "es": " (desde tu enlace)",
            "fr": " (depuis votre lien)", "de": " (über deinen Link)",
        }[lang] if from_link else ""
        return {
            "it": f"«{title_tour}»{link}: +{e} € per te.",
            "en": f"“{title_tour}”{link}: +€{e} for you.",
            "es": f"«{title_tour}»{link}: +{e} € para ti.",
            "fr": f"« {title_tour} »{link} : +{e} € pour vous.",
            "de": f"„{title_tour}“{link}: +{e} € für dich.",
        }[lang]

    texts = {
        "it": ("🐥 Hai venduto un tour!", body("it")),
        "en": ("🐥 You sold a tour!", body("en")),
        "es": ("🐥 ¡Has vendido un tour!", body("es")),
        "fr": ("🐥 Vous avez vendu un tour !", body("fr")),
        "de": ("🐥 Du hast eine Tour verkauft!", body("de")),
    }
    send_push_i18n_async(str(guide_id), texts, {"type": "tour_sold"})
