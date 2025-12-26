# routers/checkout.py

from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_UP

import stripe
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, AnyHttpUrl
from typing import Optional, Literal, Dict, Any, Tuple

from sqlalchemy.orm import Session

from app.db import get_db
from app.email_service import send_order_received_email
from models.orders import Order, OrderType, PaymentMethod, PaymentStatus
from models.order_billing_details import OrderBillingDetails

# ⬇️ Proviamo a importare Package (se esiste nel progetto)
try:
    from models.packages import Package  # type: ignore
except Exception:  # pragma: no cover
    Package = None  # type: ignore

router = APIRouter(prefix="/checkout", tags=["Checkout"])

InvoiceMode = Literal["PERSON_IT", "VAT_IT", "COMPANY_EXT"]

SUPPORTED_LANGS = {"it", "en", "es", "fr", "de"}
SITE_URL = "https://voiceguideapp.com"  # dominio pubblico del sito

# -------------------------------------------------
# Stripe config
# -------------------------------------------------
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "eur").strip().lower()

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


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


class StripeSessionIn(BaseModel):
    order_id: int
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


def _build_checkout_success_url(order_id: int, lang: str, success_url: Optional[AnyHttpUrl]) -> str:
    if success_url:
        base_success = str(success_url)
        sep = "&" if "?" in base_success else "?"
        return f"{base_success}{sep}order={order_id}"
    return f"{SITE_URL}/{lang}/checkout-success?order={order_id}"


def _build_checkout_cancel_url(order_id: int, lang: str, cancel_url: Optional[AnyHttpUrl]) -> str:
    if cancel_url:
        base_cancel = str(cancel_url)
        sep = "&" if "?" in base_cancel else "?"
        return f"{base_cancel}{sep}order={order_id}"
    return f"{SITE_URL}/{lang}/checkout?order={order_id}"


def _save_billing_from_invoice(db: Session, order_id: int, invoice: Invoice) -> None:
    if not invoice:
        return

    mode = invoice.mode
    addr = invoice.address

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
# Pricing (Fase 1: hardcoded, poi DB)
# -------------------------------------------------
PRODUCT_PRICING: Dict[str, Tuple[OrderType, Optional[int], int, Decimal]] = {
    "SINGLE_10": (OrderType.SINGLE, None, 1, Decimal("7.99")),
    "SINGLE_25": (OrderType.SINGLE, None, 1, Decimal("14.99")),
    "SINGLE_35": (OrderType.SINGLE, None, 1, Decimal("19.99")),
    "SINGLE_100": (OrderType.SINGLE, None, 1, Decimal("49.99")),
}


def _money2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _calc_amounts(product: str, partner_code: Optional[str]) -> Tuple[OrderType, Optional[int], int, Decimal, Decimal, Decimal]:
    key = (product or "").strip().upper()
    if key not in PRODUCT_PRICING:
        raise HTTPException(status_code=400, detail=f"Invalid product: {product}")

    order_type, package_id, quantity, unit_price = PRODUCT_PRICING[key]
    subtotal = _money2(unit_price * Decimal(quantity))

    discount_rate = Decimal("0.05") if (partner_code and str(partner_code).strip()) else Decimal("0.00")
    discount = _money2(subtotal * discount_rate)
    total = _money2(subtotal - discount)

    if total <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Total amount must be > 0")

    return order_type, package_id, quantity, subtotal, discount, total


def _eur_to_cents(amount_eur: Decimal) -> int:
    a = _money2(amount_eur)
    return int((a * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _resolve_single_package_id(db: Session, max_guests: int) -> int:
    """
    orders.package_id è FK -> packages.id.
    Quindi NON possiamo mettere 10/25/35/100 direttamente.
    Cerchiamo in packages una riga con max_guests = X (o equivalente).
    """
    if Package is None:
        raise HTTPException(
            status_code=500,
            detail="Package model not available. Cannot resolve package_id for SINGLE products.",
        )

    # Proviamo i nomi campo più probabili: max_guests / guests / capacity
    q = db.query(Package)
    if hasattr(Package, "max_guests"):
        row = q.filter(getattr(Package, "max_guests") == max_guests).first()
    elif hasattr(Package, "guests"):
        row = q.filter(getattr(Package, "guests") == max_guests).first()
    elif hasattr(Package, "capacity"):
        row = q.filter(getattr(Package, "capacity") == max_guests).first()
    else:
        row = None

    if not row:
        raise HTTPException(
            status_code=500,
            detail=f"Missing packages row for SINGLE_{max_guests}. Seed table 'packages' (max_guests={max_guests}).",
        )

    return int(getattr(row, "id"))


def _parse_product_to_order_fields(db: Session, product: str) -> Tuple[OrderType, Optional[int], int]:
    prod = (product or "").strip().upper()

    if prod.startswith("SINGLE_"):
        try:
            mg = int(prod.split("_", 1)[1])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product SINGLE_x")

        package_id = _resolve_single_package_id(db, max_guests=mg)
        return (OrderType.SINGLE, package_id, 1)

    if prod.startswith("PACKAGE_TO_"):
        try:
            qty = int(prod.split("_")[-1])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product PACKAGE_TO_x")
        return (OrderType.PACKAGE_TO, None, qty)

    if prod.startswith("PACKAGE_SCHOOL_"):
        try:
            qty = int(prod.split("_")[-1])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product PACKAGE_SCHOOL_x")
        return (OrderType.PACKAGE_SCHOOL, None, qty)

    key = prod
    if key in PRODUCT_PRICING:
        ot, pid, qty, _ = PRODUCT_PRICING[key]
        return ot, pid, qty

    raise HTTPException(status_code=400, detail=f"Invalid product: {product}")


# -------------------------------------------------
# POST /checkout/intent  (legacy mock)
# -------------------------------------------------
@router.post("/intent")
def create_checkout_intent(data: CheckoutIntent):
    if not data.product:
        raise HTTPException(status_code=400, detail="Invalid product")

    lang = _normalize_lang(data.lang)
    discount = 0.05 if data.customer.partner_code else 0.0

    from uuid import uuid4
    order_id = str(uuid4())

    checkout_url = _build_checkout_success_url(order_id=order_id, lang=lang, success_url=data.success_url)  # type: ignore[arg-type]

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
    if not data.product:
        raise HTTPException(status_code=400, detail="Invalid product")

    lang = _normalize_lang(data.lang)

    _, _, _, subtotal, discount, total = _calc_amounts(
        product=data.product,
        partner_code=data.customer.partner_code,
    )

    # ✅ QUI: risolviamo package_id correttamente (FK -> packages.id)
    order_type, package_id, quantity = _parse_product_to_order_fields(db, data.product)

    order = Order(
        buyer_email=data.customer.email.strip(),
        buyer_whatsapp=(data.customer.whatsapp.strip() if data.customer.whatsapp else None),

        order_type=order_type,
        package_id=package_id,
        quantity=quantity,

        subtotal_amount=float(subtotal),
        discount_amount=float(discount),
        total_amount=float(total),

        estimated_agora_cost=None,

        payment_method=PaymentMethod.OTHER,
        payment_status=PaymentStatus.PENDING,

        partner_id=None,
        referral_code=(data.customer.partner_code.strip() if data.customer.partner_code else None),
    )

    db.add(order)
    db.flush()

    if data.invoice is not None:
        _save_billing_from_invoice(db, order_id=order.id, invoice=data.invoice)

    db.commit()
    db.refresh(order)

    # Email "Order received" (best effort)
    try:
        bd = getattr(order, "billing_details", None)
        invoice_requested = bool(getattr(bd, "request_invoice", False)) if bd else False
        intestatario = getattr(bd, "company_name", None) if bd else None

        send_order_received_email(
            to_email=order.buyer_email,
            order_id=order.id,
            product=data.product,
            invoice_requested=invoice_requested,
            intestatario=intestatario,
        )
    except Exception:
        pass

    checkout_url = _build_checkout_success_url(order_id=order.id, lang=lang, success_url=data.success_url)

    return {
        "order_id": order.id,
        "discount_applied": float(discount),
        "checkout_url": checkout_url,
    }


# -------------------------------------------------
# POST /checkout/stripe/session  ✅ crea Stripe Checkout Session
# -------------------------------------------------
@router.post("/stripe/session")
def create_stripe_checkout_session(payload: StripeSessionIn, db: Session = Depends(get_db)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured (missing STRIPE_SECRET_KEY)")

    lang = _normalize_lang(payload.lang)

    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.payment_status == PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Order already paid")

    try:
        total_eur = Decimal(str(order.total_amount))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order amount")

    if total_eur <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Order total_amount must be > 0")

    amount_cents = _eur_to_cents(total_eur)

    success_url = _build_checkout_success_url(order_id=order.id, lang=lang, success_url=payload.success_url)
    cancel_url = _build_checkout_cancel_url(order_id=order.id, lang=lang, cancel_url=payload.cancel_url)

    sep = "&" if "?" in success_url else "?"
    success_url = f"{success_url}{sep}session_id={{CHECKOUT_SESSION_ID}}"

    title = f"VoiceGuide License (Order #{order.id})"

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=order.buyer_email,
            line_items=[
                {
                    "price_data": {
                        "currency": STRIPE_CURRENCY,
                        "product_data": {"name": title},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "order_id": str(order.id),
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")

    try:
        order.payment_method = PaymentMethod.STRIPE
    except Exception:
        pass

    if hasattr(order, "stripe_session_id"):
        try:
            setattr(order, "stripe_session_id", session.id)
        except Exception:
            pass

    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "order_id": order.id,
        "stripe_session_id": session.id,
        "checkout_url": session.url,
    }
