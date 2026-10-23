# app/free_tours_reminders.py
"""
Promemoria a chi si e' registrato sul sito (3 tour gratuiti) ma dopo 7 giorni
non ha ancora attivato nessun codice. Uno solo per persona.

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
from app.free_tours_emails import send_free_tours_reminder_email
from models.free_tour_signups import FreeTourSignup
from models.licenses import License
from routers.admin_free_tours import _airlink_activations
from routers.free_tours import ISSUED_BY

logger = logging.getLogger(__name__)

REMIND_AFTER_DAYS = 7
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


def due_reminders(db, now: datetime | None = None) -> list[dict] | None:
    """Chi deve ricevere il promemoria adesso; None se AirLink non risponde."""
    now = now or datetime.now(timezone.utc)
    signups = (
        db.query(FreeTourSignup)
        .filter(
            FreeTourSignup.verified_at.isnot(None),
            FreeTourSignup.verified_at <= now - timedelta(days=REMIND_AFTER_DAYS),
            FreeTourSignup.reminder_sent_at.is_(None),
            FreeTourSignup.emails_opt_out_at.is_(None),
        )
        .all()
    )
    if not signups:
        return []

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

    due = []
    for s in signups:
        lics = sorted(by_email.get(s.email_normalized, []), key=lambda x: x.max_guests)
        if not lics or any(activations.get(lic.code) for lic in lics):
            continue  # ha gia' usato almeno un codice: niente promemoria
        due.append(
            {
                "id": s.id,
                "email": s.email,
                "language": s.language,
                "licenses": [(lic.code, lic.max_guests) for lic in lics],
            }
        )
    return due


def send_due_reminders() -> int:
    """Un giro: manda i promemoria dovuti e restituisce quanti ne ha mandati."""
    db = SessionLocal()
    sent = 0
    try:
        due = due_reminders(db)
        if due is None:
            logger.warning("Promemoria tour gratuiti: AirLink non risponde, riprovo al prossimo giro")
            return 0
        for item in due:
            # Segno l'invio prima di spedire: se due giri si sovrappongono,
            # solo uno trova reminder_sent_at vuoto.
            claimed = db.execute(
                update(FreeTourSignup)
                .where(FreeTourSignup.id == item["id"], FreeTourSignup.reminder_sent_at.is_(None))
                .values(reminder_sent_at=datetime.now(timezone.utc))
            ).rowcount
            db.commit()
            if not claimed:
                continue
            try:
                send_free_tours_reminder_email(
                    to_email=item["email"],
                    licenses=item["licenses"],
                    language=item["language"],
                    unsubscribe_url=unsubscribe_url(item["id"], item["language"]),
                )
                sent += 1
            except Exception as e:
                # Libero la riga: al prossimo giro ci riprova.
                logger.error("Promemoria tour gratuiti FALLITO per id=%s: %s", item["id"], e)
                db.execute(
                    update(FreeTourSignup)
                    .where(FreeTourSignup.id == item["id"])
                    .values(reminder_sent_at=None)
                )
                db.commit()
    finally:
        db.close()
    if sent:
        logger.info("Promemoria tour gratuiti inviati: %s", sent)
    return sent


async def _loop() -> None:
    while True:
        try:
            await asyncio.to_thread(send_due_reminders)
        except Exception as e:
            logger.error("Promemoria tour gratuiti: giro fallito: %s", e)
        await asyncio.sleep(CHECK_EVERY_SECONDS)


def start_reminder_loop() -> None:
    asyncio.get_event_loop().create_task(_loop())
