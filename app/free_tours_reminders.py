# app/free_tours_reminders.py
"""
Email automatiche dopo la registrazione sul sito (3 tour gratuiti), una sola
volta ciascuna per persona:
- promemoria 7 giorni dopo, se non ha ancora attivato nessun codice;
- "com'e' andata?" + prezzi 2 giorni dopo il primo codice attivato.

Gira dentro l'app: un ciclo controlla ogni ora (start_reminder_loop, avviato
da app/main.py solo se FREE_TOURS_REMINDERS=1). L'uso dei codici si legge da
AirLink; se AirLink non risponde il giro salta e riprova l'ora dopo.
"""
import asyncio
import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db import SessionLocal
from app.free_tours_emails import send_free_tours_followup_email, send_free_tours_reminder_email
from models.free_tour_signups import FreeTourSignup
from models.licenses import License
from routers.admin_free_tours import _airlink_activations
from routers.free_tours import ISSUED_BY

logger = logging.getLogger(__name__)

REMIND_AFTER_DAYS = 7
FOLLOWUP_AFTER_DAYS = 2
CHECK_EVERY_SECONDS = 3600


def _api_base() -> str:
    explicit = os.getenv("PUBLIC_API_URL")
    if explicit:
        return explicit.rstrip("/")
    return f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'localhost:8000')}"


def unsubscribe_token(signup_id: int) -> str:
    key = f"free-tours-unsub:{os.environ['JWT_SECRET_KEY']}".encode()
    return hmac.new(key, str(signup_id).encode(), hashlib.sha256).hexdigest()[:32]


def unsubscribe_url(signup_id: int, lang: str) -> str:
    return f"{_api_base()}/free-tours/unsubscribe?id={signup_id}&t={unsubscribe_token(signup_id)}&lang={lang}"


def _parse_dt(value) -> datetime | None:
    """activated_at arriva da AirLink come stringa ISO (a volte senza fuso: e' UTC)."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def due_emails(db, now: datetime | None = None) -> dict[str, list[dict]] | None:
    """{"reminder": [...], "followup": [...]} da mandare adesso; None se AirLink non risponde."""
    now = now or datetime.now(timezone.utc)
    signups = (
        db.query(FreeTourSignup)
        .filter(
            FreeTourSignup.verified_at.isnot(None),
            FreeTourSignup.emails_opt_out_at.is_(None),
            (FreeTourSignup.reminder_sent_at.is_(None) | FreeTourSignup.followup_sent_at.is_(None)),
        )
        .all()
    )
    due: dict[str, list[dict]] = {"reminder": [], "followup": []}
    if not signups:
        return due

    emails = [s.email_normalized for s in signups]
    licenses = (
        db.query(License)
        .filter(License.issued_by_admin == ISSUED_BY, License.issued_to_email.in_(emails))
        .all()
    )
    activations = _airlink_activations([lic.code for lic in licenses])
    if activations is None:
        return None

    by_email: dict[str, list[License]] = {}
    for lic in licenses:
        by_email.setdefault(lic.issued_to_email, []).append(lic)

    for s in signups:
        lics = sorted(by_email.get(s.email_normalized, []), key=lambda x: x.max_guests)
        if not lics:
            continue
        used = [d for d in (_parse_dt(activations.get(lic.code)) for lic in lics) if d]
        unused = [(lic.code, lic.max_guests) for lic in lics if not activations.get(lic.code)]
        base = {"id": s.id, "email": s.email, "language": s.language}
        verified = s.verified_at if s.verified_at.tzinfo else s.verified_at.replace(tzinfo=timezone.utc)

        if used:
            # Ha usato almeno un codice: il promemoria non serve piu'.
            if s.followup_sent_at is None and min(used) <= now - timedelta(days=FOLLOWUP_AFTER_DAYS):
                due["followup"].append({**base, "licenses": unused})
        elif s.reminder_sent_at is None and verified <= now - timedelta(days=REMIND_AFTER_DAYS):
            due["reminder"].append({**base, "licenses": unused})
    return due


def _send_once(db, item: dict, column, send) -> bool:
    """Segna l'invio prima di spedire (due giri sovrapposti non mandano doppioni);
    se l'invio fallisce libera la riga, cosi' il giro dopo riprova."""
    claimed = db.execute(
        update(FreeTourSignup)
        .where(FreeTourSignup.id == item["id"], column.is_(None))
        .values({column.key: datetime.now(timezone.utc)})
    ).rowcount
    db.commit()
    if not claimed:
        return False
    try:
        send(
            item["email"],
            item["licenses"],
            item["language"],
            unsubscribe_url(item["id"], item["language"]),
        )
        return True
    except Exception as e:
        logger.error("Email tour gratuiti (%s) FALLITA per id=%s: %s", column.key, item["id"], e)
        db.execute(update(FreeTourSignup).where(FreeTourSignup.id == item["id"]).values({column.key: None}))
        db.commit()
        return False


def send_due_emails() -> dict[str, int]:
    """Un giro: manda le email dovute e restituisce quante per tipo."""
    db = SessionLocal()
    sent = {"reminder": 0, "followup": 0}
    try:
        due = due_emails(db)
        if due is None:
            logger.warning("Email tour gratuiti: AirLink non risponde, riprovo al prossimo giro")
            return sent
        for item in due["reminder"]:
            sent["reminder"] += _send_once(db, item, FreeTourSignup.reminder_sent_at, send_free_tours_reminder_email)
        for item in due["followup"]:
            sent["followup"] += _send_once(db, item, FreeTourSignup.followup_sent_at, send_free_tours_followup_email)
    finally:
        db.close()
    if any(sent.values()):
        logger.info("Email tour gratuiti inviate: %s", sent)
    return sent


async def _loop() -> None:
    while True:
        try:
            await asyncio.to_thread(send_due_emails)
        except Exception as e:
            logger.error("Email tour gratuiti: giro fallito: %s", e)
        await asyncio.sleep(CHECK_EVERY_SECONDS)


def start_reminder_loop() -> None:
    asyncio.get_event_loop().create_task(_loop())
