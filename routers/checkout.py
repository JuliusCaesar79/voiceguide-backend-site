# routers/checkout.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal, Dict
from uuid import uuid4

router = APIRouter(prefix="/checkout", tags=["Checkout"])

InvoiceMode = Literal["PERSON_IT", "VAT_IT", "COMPANY_EXT"]

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


@router.post("/intent")
def create_checkout_intent(data: CheckoutIntent):
    # TODO: validare prodotto da DB
    if not data.product:
        raise HTTPException(status_code=400, detail="Invalid product")

    # TODO: validare partner_code + sconto
    discount = 0.05 if data.customer.partner_code else 0.0

    # TODO: salvare order + invoice su DB
    order_id = str(uuid4())

    # TODO: generare checkout Stripe / PayPal
    checkout_url = f"https://voiceguideapp.com/it/checkout-success?order={order_id}"

    return {
        "order_id": order_id,
        "discount_applied": discount,
        "checkout_url": checkout_url
    }
