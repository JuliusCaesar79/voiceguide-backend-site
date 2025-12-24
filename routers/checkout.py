# routers/checkout.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, AnyHttpUrl
from typing import Optional, Literal, Dict
from uuid import uuid4

router = APIRouter(prefix="/checkout", tags=["Checkout"])

InvoiceMode = Literal["PERSON_IT", "VAT_IT", "COMPANY_EXT"]

SUPPORTED_LANGS = {"it", "en", "es", "fr", "de"}

SITE_URL = "https://voiceguideapp.com"  # dominio pubblico del sito


class Address(BaseModel):
    line: str
    city: str
    zip: str
    province: Optional[str] = None
    country: str


class Invoice(BaseModel):
    mode: InvoiceMode
    person_it: Optional[Dict] = None
    vat_it: Optional[Dict] = None
    company_ext: Optional[Dict] = None
    address: Address


class Customer(BaseModel):
    email: EmailStr
    whatsapp: Optional[str] = None
    partner_code: Optional[str] = None


class CheckoutIntent(BaseModel):
    product: str
    customer: Customer
    invoice: Optional[Invoice] = None

    # ✅ i18n + redirect (nuovi, retrocompatibili)
    lang: Optional[str] = "it"
    success_url: Optional[AnyHttpUrl] = None
    cancel_url: Optional[AnyHttpUrl] = None


@router.post("/intent")
def create_checkout_intent(data: CheckoutIntent):
    # TODO: validare prodotto da DB
    if not data.product:
        raise HTTPException(status_code=400, detail="Invalid product")

    # Normalize lang
    lang = (data.lang or "it").lower().strip()
    if lang not in SUPPORTED_LANGS:
        lang = "it"

    # TODO: validare partner_code + sconto
    discount = 0.05 if data.customer.partner_code else 0.0

    # TODO: salvare order + invoice su DB
    order_id = str(uuid4())

    # TODO: generare checkout Stripe / PayPal
    # ✅ per ora simuliamo il "checkout_url" come redirect alla success page
    # Priorità:
    # 1) success_url passata dal frontend
    # 2) fallback su /{lang}/checkout-success
    if data.success_url:
        base_success = str(data.success_url)
        sep = "&" if "?" in base_success else "?"
        checkout_url = f"{base_success}{sep}order={order_id}"
    else:
        checkout_url = f"{SITE_URL}/{lang}/checkout-success?order={order_id}"

    return {
        "order_id": order_id,
        "discount_applied": discount,
        "checkout_url": checkout_url
    }
