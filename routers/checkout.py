# routers/checkout.py

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, AnyHttpUrl
from typing import Optional, Literal, Dict, Any

from sqlalchemy.orm import Session

from app.db import get_db
from models.orders import Order, OrderType, PaymentMethod, PaymentStatus
from models.order_billing_details import OrderBillingDetails

router = APIRouter(prefix="/checkout", tags=["Checkout"])

InvoiceMode = Literal["PERSON_IT", "VAT_IT", "COMPANY_EXT"]

SUPPORTED_LANGS = {"it", "en", "es", "fr", "de"}
SITE_URL = "https://voiceguideapp.com"  # dominio pubblico del sito


# -----------------------------
# Pydantic models (site payload)
# -----------------------------
class Address(BaseModel):
    line: str
    city: str
    zip: str
    province: Optional[str] = None
    country: str


class Invoice(BaseModel):
    mode: InvoiceMode
    person_it: Optional[Dict[str, Any]] = None
    vat_it: Optional[Dict[str, Any]] = None
    company_ext: Optional[Dict[str, Any]] = None
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


def _normalize_lang(lang: Optional[str]) -> str:
    v = (lang or "it").lower().strip()
    return v if v in SUPPORTED_LANGS else "it"


def _normalize_country_iso2(raw: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    """
    Nel DB usiamo ISO2 (2 lettere).
    Se arriva 'Italy' o 'Germany' dal sito, prendiamo le prime 2 lettere e upper.
    (Per ora va bene per test; poi metteremo dropdown ISO2 sul sito.)
    """
    if raw is None:
        return fallback
    s = str(raw).strip()
    if not s:
        return fallback
    s2 = "".join([c for c in s if c.isalpha()])  # solo lettere
    if len(s2) < 2:
        return fallback
    return s2[:2].upper()


def _build_checkout_url(order_id: int, lang: str, success_url: Optional[AnyHttpUrl]) -> str:
    if success_url:
        base_success = str(success_url)
        sep = "&" if "?" in base_success else "?"
        return f"{base_success}{sep}order={order_id}"
    return f"{SITE_URL}/{lang}/checkout-success?order={order_id}"


def _save_billing_from_invoice(db: Session, order_id: int, invoice: Invoice) -> None:
    """
    Mappa il payload del sito (invoice.mode + blocchi) nel modello OrderBillingDetails.
    Regola concordata:
      - company_name = INTESTATARIO (persona o azienda)
      - tax_code per CF persona fisica
      - vat_number per P.IVA/VAT
    """
    if not invoice:
        return

    mode = invoice.mode
    addr = invoice.address

    # Base
    request_invoice = True

    country = None
    company_name = None
    vat_number = None
    tax_code = None
    pec = None
    sdi_code = None

    if mode == "PERSON_IT":
        country = "IT"
        person = invoice.person_it or {}
        company_name = (person.get("full_name") or "").strip() or None
        tax_code = (person.get("cf") or "").strip() or None

    elif mode == "VAT_IT":
        country = "IT"
        vat = invoice.vat_it or {}
        company_name = (vat.get("company") or "").strip() or None
        vat_number = (vat.get("vat") or "").strip() or None
        sdi_code = (vat.get("sdi") or "").strip() or None
        pec = (vat.get("pec") or "").strip() or None

    elif mode == "COMPANY_EXT":
        ext = invoice.company_ext or {}
        company_name = (ext.get("company") or "").strip() or None
        vat_number = (ext.get("vat_or_tax_id") or "").strip() or None
        country = _normalize_country_iso2(ext.get("country"))

    # Se manca intestatario in modalità fattura, lasciamo comunque salvare per test,
    # ma idealmente il frontend lo rende obbligatorio.
    bd = OrderBillingDetails(
        order_id=order_id,
        request_invoice=request_invoice,
        country=country,
        company_name=company_name,
        vat_number=vat_number,
        tax_code=tax_code,
        address=addr.line.strip() if addr.line else None,
        city=addr.city.strip() if addr.city else None,
        zip_code=addr.zip.strip() if addr.zip else None,
        province=addr.province.strip() if addr.province else None,
        pec=pec,
        sdi_code=sdi_code,
    )
    db.add(bd)


# -------------------------------------------------
# POST /checkout/intent  (legacy mock)
# -------------------------------------------------
@router.post("/intent")
def create_checkout_intent(data: CheckoutIntent):
    # TODO: validare prodotto da DB
    if not data.product:
        raise HTTPException(status_code=400, detail="Invalid product")

    lang = _normalize_lang(data.lang)

    # TODO: validare partner_code + sconto
    discount = 0.05 if data.customer.partner_code else 0.0

    # MOCK: order_id non-DB
    from uuid import uuid4
    order_id = str(uuid4())

    checkout_url = _build_checkout_url(order_id=order_id, lang=lang, success_url=data.success_url)

    return {
        "order_id": order_id,
        "discount_applied": discount,
        "checkout_url": checkout_url,
    }


# -------------------------------------------------
# POST /checkout/create-order  ✅ ordine reale (PENDING)
# -------------------------------------------------
@router.post("/create-order")
def create_order_real(data: CheckoutIntent, db: Session = Depends(get_db)):
    """
    Crea un ordine reale sul DB anche senza Stripe/PayPal:
    - payment_status=PENDING
    - payment_method=OTHER
    - total_amount=0.00 (per ora: test / pre-pagamento)
    - salva billing_details se invoice presente
    - ritorna checkout_url verso la success page con order_id REALE

    Quando collegheremo Stripe/PayPal:
    - calcoleremo importi reali
    - aggiorneremo a PAID via webhook/return
    """

    if not data.product:
        raise HTTPException(status_code=400, detail="Invalid product")

    lang = _normalize_lang(data.lang)

    # Sconto “logico” (mostrabile a UI), ma importi reali arriveranno con pricing + gateway
    discount = 0.05 if data.customer.partner_code else 0.0

    # ✅ Crea ordine DB
    order = Order(
        buyer_email=data.customer.email.strip(),
        buyer_whatsapp=(data.customer.whatsapp.strip() if data.customer.whatsapp else None),

        # Per ora: ordine generico di test (poi mapperemo product -> order_type/package/amount)
        order_type=OrderType.SINGLE,
        package_id=None,
        quantity=1,

        # breakdown (già nel model)
        subtotal_amount=0,
        discount_amount=0,

        # totale: 0.00 finché non c’è payment gateway
        total_amount=0,

        estimated_agora_cost=None,

        payment_method=PaymentMethod.OTHER,
        payment_status=PaymentStatus.PENDING,

        partner_id=None,
        referral_code=(data.customer.partner_code.strip() if data.customer.partner_code else None),
    )

    db.add(order)
    db.flush()  # otteniamo order.id senza commit

    # ✅ salva fatturazione se richiesta
    if data.invoice is not None:
        _save_billing_from_invoice(db, order_id=order.id, invoice=data.invoice)

    db.commit()
    db.refresh(order)

    # ✅ Email: se avete già una funzione email in backend, agganciala qui.
    # Non facciamo fallire l'ordine se l'email non è configurata in questa fase.
    try:
        # Esempio: from services.email import send_order_received_email
        # send_order_received_email(to=order.buyer_email, order_id=order.id)
        pass
    except Exception:
        pass

    checkout_url = _build_checkout_url(order_id=order.id, lang=lang, success_url=data.success_url)

    return {
        "order_id": order.id,
        "discount_applied": discount,
        "checkout_url": checkout_url,
    }
