# routers/checkout.py

from __future__ import annotations

import os
import re
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

# ⬇️ Import Package (tabella packages)
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

    # ✅ i18n + redirect (retrocompatibili)
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


def _normalize_product_code(raw: Optional[str]) -> str:
    """
    Normalizza product code proveniente dal sito.

    Esempi accettati:
      - single_25 / SINGLE_25 / Single-25  -> SINGLE_25
      - package_to_10 / PACKAGE-TO-10      -> PACKAGE_TO_10
      - package_school_5 / PACKAGE-SCHOOL-5-> PACKAGE_SCHOOL_5
    """
    if not raw:
        return ""
    s = str(raw).strip()
    s = s.replace("-", "_").replace(" ", "_")
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    s = s.upper()

    m = re.fullmatch(r"SINGLE(\d+)", s)
    if m:
        s = f"SINGLE_{m.group(1)}"

    m = re.fullmatch(r"PACKAGE_TO(\d+)", s)
    if m:
        s = f"PACKAGE_TO_{m.group(1)}"

    m = re.fullmatch(r"PACKAGE_SCHOOL(\d+)", s)
    if m:
        s = f"PACKAGE_SCHOOL_{m.group(1)}"

    return s


def _normalize_country_iso2(raw: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    if raw is None:
        return fallback
    s = str(raw).strip()
    if not s:
        return fallback
    s2 = "".join([c for c in s if c.isalpha()])
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


def _money2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _eur_to_cents(amount_eur: Decimal) -> int:
    a = _money2(amount_eur)
    return int((a * 100).to_integral_value(rounding=ROUND_HALF_UP))


# -------------------------------------------------
# Package resolvers (DB-driven)
# -------------------------------------------------
def _require_package_model() -> None:
    if Package is None:
        raise HTTPException(status_code=500, detail="Package model not available.")


def _resolve_single_package_id(db: Session, max_guests: int) -> int:
    """
    FIX CRITICO:
    Prima cercavamo solo max_guests==X e poteva prendere TO/SCHOOL con stessi max_guests.
    Ora filtriamo anche:
      - package_type == 'SINGLE'
      - num_licenses == 1
      - is_active == True (se presente)
    """
    _require_package_model()

    q = db.query(Package)

    if hasattr(Package, "package_type"):
        q = q.filter(getattr(Package, "package_type") == "SINGLE")

    if hasattr(Package, "num_licenses"):
        q = q.filter(getattr(Package, "num_licenses") == 1)

    if hasattr(Package, "is_active"):
        q = q.filter(getattr(Package, "is_active") == True)  # noqa

    if hasattr(Package, "max_guests"):
        q = q.filter(getattr(Package, "max_guests") == max_guests)
    else:
        raise HTTPException(status_code=500, detail="packages missing max_guests column.")

    row = q.first()
    if not row:
        raise HTTPException(
            status_code=500,
            detail=f"Missing packages row for SINGLE_{max_guests} (package_type=SINGLE, num_licenses=1).",
        )
    return int(getattr(row, "id"))


def _resolve_package_id_by_type_and_num_licenses(db: Session, package_type: str, num_licenses: int) -> int:
    """
    Per PACKAGE_TO_X e PACKAGE_SCHOOL_X:
      - package_type == 'TO' / 'SCHOOL'
      - num_licenses == X
      - is_active == True (se presente)
    """
    _require_package_model()

    q = db.query(Package)

    if hasattr(Package, "package_type"):
        q = q.filter(getattr(Package, "package_type") == package_type)

    if hasattr(Package, "num_licenses"):
        q = q.filter(getattr(Package, "num_licenses") == int(num_licenses))
    else:
        raise HTTPException(status_code=500, detail="packages missing num_licenses column.")

    if hasattr(Package, "is_active"):
        q = q.filter(getattr(Package, "is_active") == True)  # noqa

    row = q.first()
    if not row:
        raise HTTPException(
            status_code=500,
            detail=f"Missing packages row for {package_type} num_licenses={num_licenses}.",
        )
    return int(getattr(row, "id"))


def _load_package(db: Session, package_id: int) -> Any:
    _require_package_model()
    row = db.query(Package).filter(getattr(Package, "id") == int(package_id)).first()
    if not row:
        raise HTTPException(status_code=500, detail=f"Package not found (id={package_id}).")
    if hasattr(row, "is_active") and row.is_active is False:
        raise HTTPException(status_code=500, detail=f"Package id={package_id} is not active.")
    return row


def _calc_amounts_from_db(db: Session, package_id: int, units: int, partner_code: Optional[str]) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Prezzi = SEMPRE dal DB (packages.price).
    units = quantità di pacchetti acquistati (di solito 1 per i tuoi codici).
    """
    pkg = _load_package(db, package_id)

    try:
        unit_price = Decimal(str(getattr(pkg, "price")))
    except Exception:
        raise HTTPException(status_code=500, detail=f"Invalid packages.price for id={package_id}")

    subtotal = _money2(unit_price * Decimal(int(units)))

    discount_rate = Decimal("0.05") if (partner_code and str(partner_code).strip()) else Decimal("0.00")
    discount = _money2(subtotal * discount_rate)
    total = _money2(subtotal - discount)

    if total <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Total amount must be > 0")

    return subtotal, discount, total


def _parse_product_to_order_fields(db: Session, product: str) -> Tuple[OrderType, int, int]:
    """
    Ritorna: (order_type, package_id, quantity_units)

    NOTA:
    - Per SINGLE_X: quantity_units = 1 e package_id = riga SINGLE coerente
    - Per PACKAGE_TO_X: quantity_units = 1 e package_id = riga TO con num_licenses = X
    - Per PACKAGE_SCHOOL_X: idem
    """
    prod = _normalize_product_code(product)

    if prod.startswith("SINGLE_"):
        try:
            mg = int(prod.split("_", 1)[1])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product SINGLE_x")

        package_id = _resolve_single_package_id(db, max_guests=mg)
        return (OrderType.SINGLE, package_id, 1)

    if prod.startswith("PACKAGE_TO_"):
        try:
            nl = int(prod.split("_")[-1])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product PACKAGE_TO_x")

        package_id = _resolve_package_id_by_type_and_num_licenses(db, package_type="TO", num_licenses=nl)
        return (OrderType.PACKAGE_TO, package_id, 1)

    if prod.startswith("PACKAGE_SCHOOL_"):
        try:
            nl = int(prod.split("_")[-1])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product PACKAGE_SCHOOL_x")

        package_id = _resolve_package_id_by_type_and_num_licenses(db, package_type="SCHOOL", num_licenses=nl)
        return (OrderType.PACKAGE_SCHOOL, package_id, 1)

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

    resolved_product = _normalize_product_code(data.product)
    if not resolved_product:
        raise HTTPException(status_code=400, detail="Invalid product")

    # ✅ package_id corretto (fix SINGLE_25 che prendeva TO_119)
    order_type, package_id, quantity = _parse_product_to_order_fields(db, resolved_product)

    # ✅ prezzi dal DB (packages.price)
    subtotal, discount, total = _calc_amounts_from_db(
        db=db,
        package_id=package_id,
        units=quantity,
        partner_code=data.customer.partner_code,
    )

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

        payment_method=PaymentMethod.STRIPE,
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
            product=resolved_product,
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
        "resolved_product": resolved_product,
        "package_id": package_id,  # ✅ debug utile
        "total_amount": float(total),
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
