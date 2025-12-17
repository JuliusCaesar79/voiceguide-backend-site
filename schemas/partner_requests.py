# schemas/partner_requests.py

from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum
from datetime import datetime


class PartnerTier(str, Enum):
    BASE = "BASE"
    PRO = "PRO"
    ELITE = "ELITE"


class PartnerRequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# 🔓 INPUT PUBBLICO (tier commerciale scelto)
class PartnerRequestCreate(BaseModel):
    name: str
    email: EmailStr
    partner_tier: PartnerTier = PartnerTier.BASE
    notes: Optional[str] = None


# 🔒 OUTPUT (allineato al DB)
class PartnerRequestOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    partner_tier: PartnerTier
    notes: Optional[str]
    status: PartnerRequestStatus
    created_at: datetime

    class Config:
        from_attributes = True
