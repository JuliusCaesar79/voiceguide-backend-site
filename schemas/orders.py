from pydantic import BaseModel, EmailStr
from decimal import Decimal
from typing import List

from schemas.billing import BillingDetailsCreate


# --------- SINGLE LICENSE (GUIDES) ---------


class SinglePurchaseRequest(BaseModel):
    buyer_email: EmailStr
    buyer_whatsapp: str | None = None
    max_guests: int  # 10, 25, 35, 100
    quantity: int = 1
    referral_code: str | None = None  # optional partner code

    # NEW: billing details (optional)
    billing_details: BillingDetailsCreate | None = None


class SinglePurchaseResponse(BaseModel):
    order_id: int

    # Amount breakdown
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal

    # Partner
    referral_applied: bool

    payment_status: str
    license_code: str
    max_guests: int

    # WhatsApp
    whatsapp_link: str | None = None

    class Config:
        from_attributes = True


# --------- PACKAGES (TO / SCHOOL) ---------


class LicenseInfo(BaseModel):
    code: str
    max_guests: int


class PackagePurchaseRequest(BaseModel):
    buyer_email: EmailStr
    buyer_whatsapp: str | None = None
    package_type: str  # "TO" or "SCHOOL"
    bundle_size: int   # TO: 10,20,50,100 - SCHOOL: 1,5,10,30
    referral_code: str | None = None  # optional partner code

    # NEW: billing details (optional)
    billing_details: BillingDetailsCreate | None = None


class PackagePurchaseResponse(BaseModel):
    order_id: int

    # Amount breakdown
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal

    # Partner
    referral_applied: bool

    payment_status: str
    package_type: str
    bundle_size: int
    licenses: List[LicenseInfo]

    # WhatsApp
    whatsapp_link: str | None = None

    class Config:
        from_attributes = True
