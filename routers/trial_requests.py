# routers/trial_requests.py

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional

from app.db import SessionLocal
from models.trial_requests import TrialRequest, TrialRequestStatus
from models.licenses import License, LicenseType
from app.email_service import send_trial_license_email

# Riuso le stesse funzioni "source of truth" già usate dall'emissione manuale
# in admin_trial_requests.py, cosi' l'auto-emissione crea la licenza esattamente
# allo stesso modo (stesso codice, punto di innesco diverso).
from routers.admin_licenses import create_license_on_airlink, generate_license_code

router = APIRouter(prefix="", tags=["Trial Requests"])
logger = logging.getLogger(__name__)

# Taglio che viene emesso subito, senza revisione admin (basso rischio/costo).
AUTO_ISSUE_MAX_GUESTS = 5
AUTO_ISSUE_DURATION_HOURS = 24

# Un'emissione automatica per email: se ne esiste gia' una ISSUED, la nuova
# richiesta passa a revisione manuale invece di auto-emettere di nuovo.
def _already_auto_issued(db, email: str) -> bool:
    return (
        db.query(License)
        .filter(License.issued_to_email == email, License.issued_by_admin == "auto")
        .first()
        is not None
    )


class TrialRequestCreate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    email: EmailStr
    language: Literal["it", "en", "es", "fr", "de"] = "it"
    message: Optional[str] = Field(default=None, max_length=2000)
    requested_max_guests: Optional[int] = Field(default=None, ge=1, le=500)


class TrialRequestOut(BaseModel):
    id: int
    status: str
    created_at: datetime
    # Presente solo se il taglio richiesto e' stato emesso subito in automatico.
    license_code: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/trial-requests", response_model=TrialRequestOut)
def create_trial_request(payload: TrialRequestCreate):
    db = SessionLocal()
    try:
        email = str(payload.email).lower().strip()

        tr = TrialRequest(
            name=payload.name,
            email=email,
            language=payload.language,
            message=payload.message,
            requested_max_guests=payload.requested_max_guests,
            status=TrialRequestStatus.PENDING,
        )

        auto_issue = (
            payload.requested_max_guests == AUTO_ISSUE_MAX_GUESTS
            and not _already_auto_issued(db, email)
        )

        license_code: Optional[str] = None

        if auto_issue:
            max_attempts = 8
            for _ in range(max_attempts):
                candidate = generate_license_code()
                try:
                    create_license_on_airlink(candidate, AUTO_ISSUE_MAX_GUESTS)
                    license_code = candidate
                    break
                except ValueError as ve:
                    if str(ve) == "CODE_EXISTS":
                        continue
                    raise
                except Exception as e:
                    # AirLink non raggiungibile: non blocco la richiesta, resta
                    # PENDING per revisione manuale invece di fallire l'endpoint.
                    logger.error("Auto-issue trial FAILED for %s: %s", email, str(e))
                    auto_issue = False
                    break

            if auto_issue and license_code:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=AUTO_ISSUE_DURATION_HOURS)

                lic = License(
                    code=license_code,
                    license_type=LicenseType.SINGLE,
                    max_guests=AUTO_ISSUE_MAX_GUESTS,
                    duration_hours=AUTO_ISSUE_DURATION_HOURS,
                    expires_at=expires_at,
                    is_active=True,
                    issued_to_email=email,
                    notes="Trial auto-issued (5 guests)",
                    issued_by_admin="auto",
                    order_id=None,
                )
                db.add(lic)
                tr.status = TrialRequestStatus.ISSUED

        db.add(tr)
        db.commit()
        db.refresh(tr)

        if license_code:
            try:
                send_trial_license_email(
                    to_email=email,
                    license_code=license_code,
                    max_guests=AUTO_ISSUE_MAX_GUESTS,
                    name=payload.name,
                    language=payload.language,
                )
            except Exception as e:
                logger.warning("Auto-issue trial email FAILED for %s: %s", email, str(e))

        out = TrialRequestOut.model_validate(tr)
        out.license_code = license_code
        return out
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create trial request (db error)",
        )
    finally:
        db.close()
