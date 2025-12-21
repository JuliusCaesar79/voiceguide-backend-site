# schemas/partners.py

from pydantic import BaseModel, EmailStr
from decimal import Decimal
from typing import Optional
from enum import Enum
from datetime import datetime


class PartnerType(str, Enum):
    BASE = "BASE"
    PRO = "PRO"
    ELITE = "ELITE"


class PartnerCreate(BaseModel):
    name: str
    email: EmailStr
    partner_type: PartnerType = PartnerType.BASE
    commission_pct: Decimal
    referral_code: str
    notes: Optional[str] = None


class PartnerOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    partner_type: PartnerType
    commission_pct: Decimal
    referral_code: str
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True
