# routers/trial_requests.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional
from datetime import datetime

from app.db import SessionLocal
from models.trial_requests import TrialRequest, TrialRequestStatus

router = APIRouter(prefix="", tags=["Trial Requests"])


class TrialRequestCreate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    email: EmailStr
    language: Literal["it", "en"] = "it"
    message: Optional[str] = Field(default=None, max_length=2000)


class TrialRequestOut(BaseModel):
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/trial-requests", response_model=TrialRequestOut)
def create_trial_request(payload: TrialRequestCreate):
    db = SessionLocal()
    try:
        tr = TrialRequest(
            name=payload.name,
            email=str(payload.email).lower().strip(),
            language=payload.language,
            message=payload.message,
            status=TrialRequestStatus.PENDING,
        )
        db.add(tr)
        db.commit()
        db.refresh(tr)
        return tr
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create trial request (db error)",
        )
    finally:
        db.close()
