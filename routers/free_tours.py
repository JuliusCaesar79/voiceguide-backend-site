# routers/free_tours.py
"""
Registrazione gratuita dal sito: email + codice di 6 cifre -> 3 licenze
(5, 25, 35 ospiti), una sola volta per email.

POST /free-tours/start   {email, lang}        -> manda il codice
POST /free-tours/verify  {email, code, lang}  -> crea e manda le 3 licenze (e le restituisce)

Protezioni (approvate da Stefano il 2026-10-23): domini usa e getta bloccati,
email normalizzate (alias Gmail e +tag contano come la stessa casella),
limiti per indirizzo IP, registrazioni visibili in dashboard.
Errori: il "detail" e' una parola chiave che il frontend traduce
(invalid_email, already_claimed, invalid_code, rate_limited).
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.email_guard import is_disposable, normalize_email
from app.free_tours_emails import send_free_tours_code_email, send_free_tours_licenses_email
from models.free_tour_signups import FreeTourSignup
from models.licenses import License, LicenseType
from routers.admin_licenses import create_license_on_airlink, generate_license_code

router = APIRouter(prefix="/free-tours", tags=["Free tours"])
logger = logging.getLogger(__name__)

FREE_TIERS = (5, 25, 35)
CODE_TTL_MINUTES = 15
MAX_ATTEMPTS = 5
MAX_CODES_PER_EMAIL_PER_HOUR = 5
MAX_CODES_PER_IP_PER_HOUR = 10
MAX_CLAIMS_PER_IP_PER_DAY = 1
ISSUED_BY = "free_signup"

Lang = Literal["it", "en", "es", "fr", "de"]


class StartIn(BaseModel):
    email: EmailStr
    lang: Lang = "it"


class VerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    lang: Lang = "it"


def _client_ip(request: Request) -> str | None:
    # Dietro il proxy di Railway l'IP reale e' il primo di X-Forwarded-For
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def _hash(email_normalized: str, code: str) -> str:
    return hashlib.sha256(f"{email_normalized}:{code}".encode()).hexdigest()


def _already_claimed(db, email_normalized: str) -> bool:
    if db.query(FreeTourSignup).filter(FreeTourSignup.claimed_email == email_normalized).first():
        return True
    return (
        db.query(License)
        .filter(License.issued_to_email == email_normalized, License.issued_by_admin == ISSUED_BY)
        .first()
        is not None
    )


@router.post("/start")
def start(payload: StartIn, request: Request):
    email = str(payload.email).strip()
    email_n = normalize_email(email)
    if is_disposable(email_n):
        raise HTTPException(status_code=400, detail="invalid_email")

    ip = _client_ip(request)
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)

    db = SessionLocal()
    try:
        if _already_claimed(db, email_n):
            raise HTTPException(status_code=409, detail="already_claimed")

        recent_email = (
            db.query(FreeTourSignup)
            .filter(FreeTourSignup.email_normalized == email_n, FreeTourSignup.created_at >= hour_ago)
            .count()
        )
        recent_ip = (
            db.query(FreeTourSignup)
            .filter(FreeTourSignup.ip_address == ip, FreeTourSignup.created_at >= hour_ago)
            .count()
            if ip
            else 0
        )
        if recent_email >= MAX_CODES_PER_EMAIL_PER_HOUR or recent_ip >= MAX_CODES_PER_IP_PER_HOUR:
            raise HTTPException(status_code=429, detail="rate_limited")

        code = f"{secrets.randbelow(1_000_000):06d}"
        row = FreeTourSignup(
            email=email,
            email_normalized=email_n,
            language=payload.lang,
            code_hash=_hash(email_n, code),
            code_expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
            attempts=0,
            ip_address=ip,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    try:
        send_free_tours_code_email(to_email=email, code=code, language=payload.lang)
    except Exception as e:
        logger.error("Free tours code email FAILED for %s: %s", email, e)
        raise HTTPException(status_code=502, detail="email_failed")

    return {"ok": True}


@router.post("/verify")
def verify(payload: VerifyIn, request: Request):
    email = str(payload.email).strip()
    email_n = normalize_email(email)
    ip = _client_ip(request)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        if _already_claimed(db, email_n):
            raise HTTPException(status_code=409, detail="already_claimed")

        row = (
            db.query(FreeTourSignup)
            .filter(FreeTourSignup.email_normalized == email_n, FreeTourSignup.verified_at.is_(None))
            .order_by(FreeTourSignup.id.desc())
            .first()
        )
        expires = row.code_expires_at if row else None
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if not row or expires <= now or row.attempts >= MAX_ATTEMPTS:
            raise HTTPException(status_code=400, detail="invalid_code")

        if not secrets.compare_digest(row.code_hash, _hash(email_n, payload.code)):
            row.attempts += 1
            db.commit()
            raise HTTPException(status_code=400, detail="invalid_code")

        if ip:
            claims_today = (
                db.query(FreeTourSignup)
                .filter(
                    FreeTourSignup.ip_address == ip,
                    FreeTourSignup.verified_at >= now - timedelta(days=1),
                )
                .count()
            )
            if claims_today >= MAX_CLAIMS_PER_IP_PER_DAY:
                raise HTTPException(status_code=429, detail="rate_limited")

        # Prenoto l'email prima di creare le licenze: il vincolo UNIQUE su
        # claimed_email blocca una seconda conferma in parallelo.
        row.verified_at = now
        row.claimed_email = email_n
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="already_claimed")

        issued: list[tuple[str, int]] = []
        try:
            for max_guests in FREE_TIERS:
                for _ in range(8):
                    candidate = generate_license_code()
                    try:
                        create_license_on_airlink(candidate, max_guests)
                        issued.append((candidate, max_guests))
                        break
                    except ValueError as ve:
                        if str(ve) == "CODE_EXISTS":
                            continue
                        raise
                else:
                    raise RuntimeError("could not generate a unique license code")
        except Exception as e:
            # AirLink non raggiungibile: libero l'email cosi' l'utente puo'
            # riprovare. Eventuali codici gia' creati restano inattivi su AirLink.
            logger.error("Free tours AirLink FAILED for %s: %s (issued %s)", email_n, e, issued)
            row.verified_at = None
            row.claimed_email = None
            db.commit()
            raise HTTPException(status_code=502, detail="airlink_failed")

        for code, max_guests in issued:
            db.add(
                License(
                    code=code,
                    license_type=LicenseType.SINGLE,
                    max_guests=max_guests,
                    duration_hours=4,
                    expires_at=None,  # i codici non scadono finche' non vengono attivati
                    is_active=True,
                    issued_to_email=email_n,
                    notes=f"Registrazione gratuita sito (3 tour) — {email}",
                    issued_by_admin=ISSUED_BY,
                    order_id=None,
                )
            )
        row.license_codes = ",".join(code for code, _ in issued)
        db.commit()
    finally:
        db.close()

    try:
        send_free_tours_licenses_email(to_email=email, licenses=issued, language=payload.lang)
    except Exception as e:
        # Le licenze esistono gia': l'admin le vede in dashboard e puo' rimandarle.
        logger.error("Free tours licenses email FAILED for %s: %s", email, e)

    # I codici tornano anche al sito, che li mostra subito: l'email puo'
    # finire in spam (successo con Yahoo il 2026-10-23).
    return {
        "ok": True,
        "licenses": [{"code": code, "max_guests": n} for code, n in issued],
    }
