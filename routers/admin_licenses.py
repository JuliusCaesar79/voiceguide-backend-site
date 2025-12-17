# routers/admin_licenses.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import uuid
import logging
import os
import requests

from app.db import get_db
from models.licenses import License
from schemas.licenses_admin import AdminLicenseCreate, AdminLicenseOut
from app.email_service import send_trial_license_email

router = APIRouter(prefix="/admin/licenses", tags=["Admin - Licenses"])
logger = logging.getLogger(__name__)

AIRLINK_TOUR_DURATION_MINUTES = 240  # 4h fisse (durata tour)


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name, default)
    if v in ("", None):
        return default
    return v


def generate_license_code() -> str:
    raw = uuid.uuid4().hex[:8].upper()
    return f"VG-LIC-{raw}"


def create_license_on_airlink(code: str, max_listeners: int) -> None:
    """
    Crea la licenza sul backend AirLink (produzione Railway).
    Auth: header X-Admin-Secret
    Endpoint: POST /api/admin/licenses
    """
    base_url = _env("AIRLINK_BASE_URL")
    admin_secret = _env("AIRLINK_ADMIN_SECRET")
    if not base_url or not admin_secret:
        raise RuntimeError("AIRLINK_BASE_URL / AIRLINK_ADMIN_SECRET mancanti nelle env del Site.")

    url = f"{base_url.rstrip('/')}/api/admin/licenses"
    headers = {"X-Admin-Secret": admin_secret}

    body = {
        "code": code,
        "max_listeners": max_listeners,
        "duration_minutes": AIRLINK_TOUR_DURATION_MINUTES,
        "is_active": False,  # verrà attivata dall'app con /api/activate-license
    }

    r = requests.post(url, json=body, headers=headers, timeout=15)

    # se già esiste codice, lo trattiamo come conflitto (alcuni backend usano 400/409)
    if r.status_code in (409,):
        raise ValueError("CODE_EXISTS")

    if r.status_code >= 400:
        raise RuntimeError(f"AirLink error {r.status_code}: {r.text}")


@router.post("/manual", response_model=AdminLicenseOut)
def create_manual_license(payload: AdminLicenseCreate, db: Session = Depends(get_db)):
    # 1) genera code e crea su AirLink (source of truth)
    max_attempts = 8
    code = None

    for _ in range(max_attempts):
        candidate = generate_license_code()
        try:
            create_license_on_airlink(candidate, payload.max_guests)
            code = candidate
            break
        except ValueError as ve:
            if str(ve) == "CODE_EXISTS":
                continue
            raise
        except Exception as e:
            logger.error("AirLink create license failed: %s", str(e))
            raise HTTPException(status_code=502, detail=f"AirLink create license failed: {str(e)}")

    if not code:
        raise HTTPException(status_code=500, detail="Could not generate a unique license code.")

    # 2) validità trial lato Site (finestra per attivare, es. 24h)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.duration_hours)
    expires_at_iso = expires_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # 3) salva shadow record nel Site (storico/admin/email/notes)
    lic = License(
        code=code,
        license_type=payload.license_type,
        max_guests=payload.max_guests,
        duration_hours=payload.duration_hours,  # validità trial
        expires_at=expires_at,
        is_active=True,
        issued_to_email=payload.issued_to_email,
        notes=payload.notes,
        issued_by_admin="admin",
        order_id=None,
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)

    # 4) email NON BLOCCANTE (HTML + TEXT)
    if payload.send_email:
        try:
            send_trial_license_email(
                to_email=payload.issued_to_email,
                license_code=code,
                max_guests=payload.max_guests,
                duration_hours=payload.duration_hours,
                expires_at_iso=expires_at_iso,
            )
        except Exception as e:
            logger.warning("Trial license email failed for %s: %s", payload.issued_to_email, str(e))

    return lic
