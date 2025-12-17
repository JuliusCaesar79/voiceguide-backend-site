from pydantic import BaseModel, EmailStr
from decimal import Decimal


class PartnerCreate(BaseModel):
    name: str
    email: EmailStr
    partner_type: str  # BASE, PRO, ELITE
    commission_pct: Decimal
    referral_code: str
    notes: str | None = None


class PartnerOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    partner_type: str
    commission_pct: Decimal
    referral_code: str
    is_active: bool

    class Config:
        from_attributes = True
