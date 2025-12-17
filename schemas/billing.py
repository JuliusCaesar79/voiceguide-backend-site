# schemas/billing.py

from typing import Optional
from pydantic import BaseModel, Field


class BillingDetailsBase(BaseModel):
    request_invoice: bool = Field(default=False)

    # Dati generali
    country: Optional[str] = Field(default=None, min_length=2, max_length=2)  # ISO2: IT, FR, DE
    company_name: Optional[str] = None

    # Italia / EU
    vat_number: Optional[str] = None
    tax_code: Optional[str] = None

    # Indirizzo
    address: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    province: Optional[str] = None

    # Italia (fatturazione elettronica)
    pec: Optional[str] = None
    sdi_code: Optional[str] = None


class BillingDetailsCreate(BillingDetailsBase):
    """Usato in input sugli endpoint /purchase/*"""
    pass


class BillingDetailsOut(BillingDetailsBase):
    """Usato in output (lettura ordine)"""
    id: int
    order_id: int

    class Config:
        from_attributes = True  # SQLAlchemy compatibility
