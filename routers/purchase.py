from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal, ROUND_HALF_UP
import uuid
import os
import logging
from typing import Any

import requests

from app.db import get_db
from app.email_service import send_receipt_email
from app.email_templates import (
    render_receipt_html_single,
    render_receipt_html_package,
)
from app.whatsapp_templates import build_whatsapp_message

from schemas.orders import (
    SinglePurchaseRequest,
    SinglePurchaseResponse,
    PackagePurchaseRequest,
    PackagePurchaseResponse,
    LicenseInfo,
)

# NEW: billing schema + model
from schemas.billing import BillingDetailsCreate
from models.order_billing_details import OrderBillingDetails

from models.orders import Order, OrderType, PaymentMethod, PaymentStatus
from models.licenses import License, LicenseType
from models.partners import Partner
from models.partner_payouts import PartnerPayout

router = APIRouter(prefix="/purchase", tags=["Purchase"])
logger = logging.getLogger(__name__)


# -------------------------------------------------
# PRICING
# -------------------------------------------------

LICENSE_PRICES: dict[int, Decimal] = {
    10: Decimal("7.99"),
    25: Decimal("14.99"),
    35: Decimal("19.99"),
    100: Decimal("49.99"),
}

TO_PACKAGES: dict[int, Decimal] = {
    10: Decimal("119"),
    20: Decimal("225"),
    50: Decimal("525"),
    100: Decimal("975"),
}

SCHOOL_PACKAGES: dict[int, Decimal] = {
    1: Decimal("29.99"),
    5: Decimal("135"),
    10: Decimal("249"),
    30: Decimal("675"),
}

# -------------------------------------------------
# AGORA COST (internal)
# -------------------------------------------------

AGORA_AUDIO_PRICE_PER_1000_MIN = Decimal("0.99")
STANDARD_TOUR_MINUTES = 240  # 4 hours

# -------------------------------------------------
# PARTNER DISCOUNT
# -------------------------------------------------

PARTNER_DISCOUNT_PCT = Decimal("5")  # 5%


# -------------------------------------------------
# AIRLINK BRIDGE (Site -> AirLink)
# -------------------------------------------------

def _get_env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name, default)
    if v in ("", None):
        return default
    return v


def _airlink_create_license(
    *,
    code: str,
    max_listeners: int,
    duration_minutes: int = STANDARD_TOUR_MINUTES,
) -> dict[str, Any]:
    """
    Crea la licenza su AirLink (backend app), così l'app la trova subito.

    Richiede env:
      - AIRLINK_BASE_URL (es: https://voiceguide-airlink-backend-production.up.railway.app)
      - AIRLINK_ADMIN_SECRET (stesso valore usato in AirLink per X-Admin-Secret)
    """
    base = _get_env("AIRLINK_BASE_URL")
    secret = _get_env("AIRLINK_ADMIN_SECRET")

    if not base or not secret:
        raise RuntimeError("AIRLINK_BASE_URL / AIRLINK_ADMIN_SECRET mancanti nel .env")

    # ✅ endpoint corretto da Swagger AirLink
    url = base.rstrip("/") + "/api/admin/licenses"

    payload = {
        "code": code,
        "max_listeners": max_listeners,
        "duration_minutes": duration_minutes,
        "is_active": False,
    }

    headers = {
        "X-Admin-Secret": secret,
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
    except Exception as e:
        raise RuntimeError(f"AirLink request failed: {e}") from e

    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"AirLink error {r.status_code}: {detail}")

    return r.json() if r.content else {}


def generate_license_code() -> str:
    raw = uuid.uuid4().hex[:8].upper()
    return f"VG-LIC-{raw}"


# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def money2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def estimate_agora_cost_for_single_license(max_guests: int) -> Decimal:
    participants = max_guests + 1
    total_minutes = Decimal(participants * STANDARD_TOUR_MINUTES)
    cost = (total_minutes / Decimal("1000")) * AGORA_AUDIO_PRICE_PER_1000_MIN
    return money2(cost)


def estimate_agora_cost_for_package(num_licenses: int, max_guests_per_license: int) -> Decimal:
    per_license = estimate_agora_cost_for_single_license(max_guests_per_license)
    return money2(per_license * Decimal(num_licenses))


def get_active_partner_by_code(db: Session, referral_code: str | None) -> Partner | None:
    if not referral_code:
        return None
    return (
        db.query(Partner)
        .filter(
            Partner.referral_code == referral_code,
            Partner.is_active == True,  # noqa
        )
        .first()
    )


def calc_partner_discount(subtotal: Decimal, partner: Partner | None) -> Decimal:
    if not partner:
        return Decimal("0.00")
    return money2((subtotal * PARTNER_DISCOUNT_PCT) / Decimal("100"))


def save_billing_details_if_requested(
    db: Session,
    order_id: int,
    billing_details: BillingDetailsCreate | None,
) -> None:
    """
    Salva i dati fatturazione solo se:
    - billing_details presente
    - request_invoice == True
    """
    if not billing_details:
        return
    if not getattr(billing_details, "request_invoice", False):
        return

    billing = OrderBillingDetails(
        order_id=order_id,
        request_invoice=True,
        country=billing_details.country,
        company_name=billing_details.company_name,
        vat_number=billing_details.vat_number,
        tax_code=billing_details.tax_code,
        address=billing_details.address,
        city=billing_details.city,
        zip_code=billing_details.zip_code,
        province=billing_details.province,
        pec=billing_details.pec,
        sdi_code=billing_details.sdi_code,
    )
    db.add(billing)
    db.commit()


# =================================================
# SINGLE LICENSE PURCHASE
# =================================================

@router.post("/single", response_model=SinglePurchaseResponse)
def purchase_single(payload: SinglePurchaseRequest, db: Session = Depends(get_db)):
    price = LICENSE_PRICES.get(payload.max_guests)
    if price is None:
        raise HTTPException(status_code=400, detail="Invalid license type.")

    subtotal = money2(price * payload.quantity)
    partner = get_active_partner_by_code(db, payload.referral_code)
    discount = calc_partner_discount(subtotal, partner)
    total = money2(subtotal - discount)

    new_order = Order(
        buyer_email=payload.buyer_email,
        buyer_whatsapp=payload.buyer_whatsapp,
        order_type=OrderType.SINGLE,
        quantity=payload.quantity,
        subtotal_amount=subtotal,
        discount_amount=discount,
        total_amount=total,
        estimated_agora_cost=estimate_agora_cost_for_single_license(payload.max_guests),
        payment_method=PaymentMethod.STRIPE,
        payment_status=PaymentStatus.PAID,
        partner_id=partner.id if partner else None,
        referral_code=payload.referral_code if partner else None,
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # --- BILLING DETAILS (opzionali, retro-compatibili) ---
    billing_details = getattr(payload, "billing_details", None)
    save_billing_details_if_requested(db, new_order.id, billing_details)

    if partner:
        payout = PartnerPayout(
            partner_id=partner.id,
            order_id=new_order.id,
            amount=money2((total * Decimal(str(partner.commission_pct))) / Decimal("100")),
            paid=False,
        )
        db.add(payout)
        db.commit()

    # ✅ crea licenza/e su AirLink + salva nel Site DB
    created_codes: list[str] = []

    for _ in range(payload.quantity):
        license_code = generate_license_code()

        # 1) AIRLINK (app backend)
        try:
            _airlink_create_license(
                code=license_code,
                max_listeners=payload.max_guests,
                duration_minutes=STANDARD_TOUR_MINUTES,
            )
        except Exception as e:
            logger.error(
                "AirLink sync FAILED (single) order=%s code=%s err=%s",
                new_order.id,
                license_code,
                str(e),
            )
            raise HTTPException(
                status_code=502,
                detail="License sync to AirLink failed. No email was sent. Please retry.",
            )

        # 2) SITE DB
        license_obj = License(
            code=license_code,
            license_type=LicenseType.SINGLE,
            max_guests=payload.max_guests,
            order_id=new_order.id,
        )
        db.add(license_obj)
        created_codes.append(license_code)

    db.commit()

    # Per compatibilità response attuale: se qty=1 ritorniamo il primo
    license_code_for_response = created_codes[0] if created_codes else ""

    # ---------------- EMAIL ----------------
    try:
        subject = f"VoiceGuideApp — Purchase completed (Order #{new_order.id})"

        text_body = (
            f"Thank you for your purchase on VoiceGuideApp.\n\n"
            f"Order: #{new_order.id}\n"
            f"Total: {new_order.total_amount} EUR\n"
            f"License: {license_code_for_response}\n"
            f"Max guests: {payload.max_guests}\n\n"
            f"Open the VoiceGuideApp, enter the license code and start your tour.\n"
        )

        html_body = render_receipt_html_single(
            order_id=new_order.id,
            total_amount=new_order.total_amount,
            license_code=license_code_for_response,
            max_guests=payload.max_guests,
        )

        send_receipt_email(payload.buyer_email, subject, text_body, html_body=html_body)
    except Exception as e:
        print("EMAIL ERROR (single):", repr(e))

    # ---------------- WHATSAPP ----------------
    raw_whatsapp_text = f"""
VoiceGuideApp ✅ Purchase completed

Order: #{new_order.id}
Total: {new_order.total_amount} €
License: {license_code_for_response}
Max guests: {payload.max_guests}

Quick instructions:
1) Open the VoiceGuideApp
2) Enter the license code
3) Start the tour and share the PIN with your guests

Need help?
support@voiceguideapp.com
"""

    whatsapp_message = build_whatsapp_message(raw_whatsapp_text)
    whatsapp_link = f"https://wa.me/?text={whatsapp_message}"

    return SinglePurchaseResponse(
        order_id=new_order.id,
        subtotal_amount=new_order.subtotal_amount,
        discount_amount=new_order.discount_amount,
        total_amount=new_order.total_amount,
        referral_applied=bool(partner),
        payment_status=new_order.payment_status.value,
        license_code=license_code_for_response,
        max_guests=payload.max_guests,
        whatsapp_link=whatsapp_link,
    )


# =================================================
# PACKAGE PURCHASE (TO / SCHOOL)
# =================================================

@router.post("/package", response_model=PackagePurchaseResponse)
def purchase_package(payload: PackagePurchaseRequest, db: Session = Depends(get_db)):
    package_type = payload.package_type.upper()

    if package_type == "TO":
        price_map = TO_PACKAGES
        order_type = OrderType.PACKAGE_TO
        license_type = LicenseType.TO
        max_guests = 25
    elif package_type == "SCHOOL":
        price_map = SCHOOL_PACKAGES
        order_type = OrderType.PACKAGE_SCHOOL
        license_type = LicenseType.SCHOOL
        max_guests = 100
    else:
        raise HTTPException(status_code=400, detail="Invalid package_type.")

    price = price_map.get(payload.bundle_size)
    if price is None:
        raise HTTPException(status_code=400, detail="Invalid bundle_size.")

    subtotal = money2(price)
    partner = get_active_partner_by_code(db, payload.referral_code)
    discount = calc_partner_discount(subtotal, partner)
    total = money2(subtotal - discount)

    new_order = Order(
        buyer_email=payload.buyer_email,
        buyer_whatsapp=payload.buyer_whatsapp,
        order_type=order_type,
        quantity=payload.bundle_size,
        subtotal_amount=subtotal,
        discount_amount=discount,
        total_amount=total,
        estimated_agora_cost=estimate_agora_cost_for_package(payload.bundle_size, max_guests),
        payment_method=PaymentMethod.STRIPE,
        payment_status=PaymentStatus.PAID,
        partner_id=partner.id if partner else None,
        referral_code=payload.referral_code if partner else None,
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # --- BILLING DETAILS (opzionali, retro-compatibili) ---
    billing_details = getattr(payload, "billing_details", None)
    save_billing_details_if_requested(db, new_order.id, billing_details)

    if partner:
        payout = PartnerPayout(
            partner_id=partner.id,
            order_id=new_order.id,
            amount=money2((total * Decimal(str(partner.commission_pct))) / Decimal("100")),
            paid=False,
        )
        db.add(payout)
        db.commit()

    licenses: list[LicenseInfo] = []

    for _ in range(payload.bundle_size):
        code = generate_license_code()

        # 1) AIRLINK (app backend)
        try:
            _airlink_create_license(
                code=code,
                max_listeners=max_guests,
                duration_minutes=STANDARD_TOUR_MINUTES,
            )
        except Exception as e:
            logger.error(
                "AirLink sync FAILED (package) order=%s code=%s err=%s",
                new_order.id,
                code,
                str(e),
            )
            raise HTTPException(
                status_code=502,
                detail="License sync to AirLink failed. No email was sent. Please retry.",
            )

        # 2) SITE DB
        lic = License(
            code=code,
            license_type=license_type,
            max_guests=max_guests,
            order_id=new_order.id,
        )
        db.add(lic)
        licenses.append(LicenseInfo(code=code, max_guests=max_guests))

    db.commit()

    # ---------------- EMAIL ----------------
    try:
        subject = f"VoiceGuideApp — Purchase completed (Order #{new_order.id})"

        text_body = (
            f"Thank you for your purchase on VoiceGuideApp.\n\n"
            f"Order: #{new_order.id}\n"
            f"Total: {new_order.total_amount} EUR\n"
            f"Package: {package_type}\n"
            f"Quantity: {payload.bundle_size}\n\n"
            f"Open the VoiceGuideApp, enter a license code and start your tour.\n"
        )

        html_body = render_receipt_html_package(
            order_id=new_order.id,
            total_amount=new_order.total_amount,
            package_type=package_type,
            bundle_size=payload.bundle_size,
            licenses_lines=[f"{x.code} (max guests: {x.max_guests})" for x in licenses],
        )

        send_receipt_email(payload.buyer_email, subject, text_body, html_body=html_body)
    except Exception as e:
        print("EMAIL ERROR (package):", repr(e))

    # ---------------- WHATSAPP ----------------
    licenses_text = "\n".join([f"- {x.code}" for x in licenses])

    raw_whatsapp_text = f"""
VoiceGuideApp ✅ Purchase completed

Order: #{new_order.id}
Total: {new_order.total_amount} €
Package: {package_type}
Quantity: {payload.bundle_size}

License codes:
{licenses_text}

Quick instructions:
1) Open the VoiceGuideApp
2) Enter one of the license codes
3) Start the tour and share the PIN with your guests

Need help?
support@voiceguideapp.com
"""

    whatsapp_message = build_whatsapp_message(raw_whatsapp_text)
    whatsapp_link = f"https://wa.me/?text={whatsapp_message}"

    return PackagePurchaseResponse(
        order_id=new_order.id,
        subtotal_amount=new_order.subtotal_amount,
        discount_amount=new_order.discount_amount,
        total_amount=new_order.total_amount,
        referral_applied=bool(partner),
        payment_status=new_order.payment_status.value,
        package_type=package_type,
        bundle_size=payload.bundle_size,
        licenses=licenses,
        whatsapp_link=whatsapp_link,
    )
