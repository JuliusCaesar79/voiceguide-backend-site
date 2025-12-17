# routers/admin_trial_requests.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy.orm import Session

from app.db import get_db
from models.trial_requests import TrialRequest, TrialRequestStatus
from models.admin import Admin

from routers.auth_admin import get_current_admin

from models.licenses import License, LicenseType
from app.email_service import send_trial_license_email

# ✅ Riutilizziamo la stessa funzione “source of truth” di admin_licenses.py
from routers.admin_licenses import create_license_on_airlink, generate_license_code

router = APIRouter(prefix="/admin", tags=["Admin - Trial Requests"])
logger = logging.getLogger(__name__)


# -------------------------
# Schemas
# -------------------------
class TrialRequestRow(BaseModel):
    id: int
    name: Optional[str]
    email: str
    language: str
    message: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class IssueTrialPayload(BaseModel):
    license_type: Literal["SINGLE", "TO", "SCHOOL", "MUSEUM"] = "SINGLE"
    max_guests: int = Field(default=10, ge=1, le=500)
    duration_hours: int = Field(default=24, ge=1, le=720)
    notes: Optional[str] = Field(default=None, max_length=2000)
    send_email: bool = True


class RejectPayload(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class IssueResult(BaseModel):
    trial_request_id: int
    new_status: str
    license_code: str
    expires_at_iso: str


# -------------------------
# Endpoints
# -------------------------
@router.get("/trial-requests", response_model=List[TrialRequestRow])
def list_trial_requests(
    status: Optional[Literal["PENDING", "ISSUED", "REJECTED"]] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(TrialRequest)
    if status:
        q = q.filter(TrialRequest.status == TrialRequestStatus(status))
    q = q.order_by(TrialRequest.created_at.desc())
    return q.all()


@router.post("/trial-requests/{trial_request_id}/reject", response_model=TrialRequestRow)
def reject_trial_request(
    trial_request_id: int,
    payload: RejectPayload,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    tr = db.query(TrialRequest).filter(TrialRequest.id == trial_request_id).first()
    if not tr:
        raise HTTPException(status_code=404, detail="Trial request not found")

    if tr.status != TrialRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Cannot reject request in status {tr.status}")

    tr.status = TrialRequestStatus.REJECTED

    if payload.reason:
        if tr.message:
            tr.message = f"{tr.message}\n\n[ADMIN REJECT REASON] {payload.reason}"
        else:
            tr.message = f"[ADMIN REJECT REASON] {payload.reason}"

    db.commit()
    db.refresh(tr)
    return tr


@router.post("/trial-requests/{trial_request_id}/issue", response_model=IssueResult)
def issue_trial_request(
    trial_request_id: int,
    payload: IssueTrialPayload,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    tr = db.query(TrialRequest).filter(TrialRequest.id == trial_request_id).first()
    if not tr:
        raise HTTPException(status_code=404, detail="Trial request not found")

    if tr.status != TrialRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Cannot issue request in status {tr.status}")

    # 1) genera code + crea su AirLink (source of truth)
    max_attempts = 8
    code = None

    for _ in range(max_attempts):
        candidate = generate_license_code()
        try:
            create_license_on_airlink(candidate, payload.max_guests)
            code = candidate
            break
        except ValueError as ve:
            # admin_licenses usa CODE_EXISTS
            if str(ve) == "CODE_EXISTS":
                continue
            raise
        except Exception as e:
            logger.error("AirLink create license failed: %s", str(e))
            raise HTTPException(status_code=502, detail=f"AirLink create license failed: {str(e)}")

    if not code:
        raise HTTPException(status_code=500, detail="Could not generate a unique license code.")

    # 2) validità trial lato Site (finestra admin)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.duration_hours)
    expires_at_iso = expires_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # 3) salva shadow record License nel Site
    lic = License(
        code=code,
        license_type=LicenseType(payload.license_type),
        max_guests=payload.max_guests,
        duration_hours=payload.duration_hours,
        expires_at=expires_at,
        is_active=True,
        issued_to_email=tr.email,
        notes=payload.notes,
        issued_by_admin=getattr(admin, "email", None) or "admin",
        order_id=None,
    )
    db.add(lic)

    # 4) marca TrialRequest come ISSUED
    tr.status = TrialRequestStatus.ISSUED

    db.commit()

    # 5) email NON BLOCCANTE
    if payload.send_email:
        try:
            send_trial_license_email(
                to_email=tr.email,
                license_code=code,
                max_guests=payload.max_guests,
                duration_hours=payload.duration_hours,
                expires_at_iso=expires_at_iso,
            )
        except Exception as e:
            logger.warning("Trial license email failed for %s: %s", tr.email, str(e))

    return IssueResult(
        trial_request_id=tr.id,
        new_status=tr.status.value,
        license_code=code,
        expires_at_iso=expires_at_iso,
    )


# ✅ NEW: badge/count endpoint per sidebar/dashboard admin
@router.get("/trial-requests/count")
def count_trial_requests(
    status: Optional[Literal["PENDING", "ISSUED", "REJECTED"]] = "PENDING",
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(TrialRequest)
    if status:
        q = q.filter(TrialRequest.status == TrialRequestStatus(status))
    return {"status": status, "count": q.count()}
