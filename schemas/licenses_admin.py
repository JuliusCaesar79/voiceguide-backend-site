# schemas/licenses_admin.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


class AdminLicenseType(str, Enum):
    SINGLE = "SINGLE"
    TO = "TO"
    SCHOOL = "SCHOOL"
    MUSEUM = "MUSEUM"


class AdminLicenseCreate(BaseModel):
    issued_to_email: EmailStr
    license_type: AdminLicenseType
    max_guests: int
    duration_hours: int = 24  # default trial
    notes: Optional[str] = "Trial request"
    send_email: bool = True


class AdminLicenseOut(BaseModel):
    id: int
    code: str
    license_type: AdminLicenseType
    max_guests: int
    duration_hours: int
    expires_at: Optional[datetime]
    is_active: bool
    issued_to_email: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True
