# app/fulfillment_service.py

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import os
import uuid
import logging
from typing import Any, Optional

import requests
from sqlalchemy.orm import Session

from models.orders import Order, OrderType, PaymentMethod, PaymentStatus
from models.licenses import License, LicenseType
from models.partners import Partner
from models.partner_payouts import PartnerPayout

from app.email_service import send_payment_received_email

logger = logging.getLogger(__name__)

# -----------------------------
# PRICING (allineato a purchase.py)
# -----------------------------
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

# -----------------------------
# AGORA COST (internal)
# -----------------------------
AGORA_AUDIO_PRICE_PER_1000_MIN = Decimal("0.99")
STANDARD_TOUR_MINUTES = 240  # 4 hours

# PARTNER DISCOUNT (5%)
PARTNER_DISCOUNT_PCT = Decimal("5")


def _get_env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name, default)
    if v in ("", None):
        return default
    return v


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


def generate_license_code() -> str:
    raw = uuid.uuid4().hex[:8].upper()
    return f"VG-LIC-{raw}"


def _airlink_create_license(
    *,
    code: str,
    max_listeners: int,
    duration_minutes: int = STANDARD_TOUR_MINUTES,
) -> dict[str, Any]:
    base = _get_env("AIRLINK_BASE_URL")
    secret = _get_env("AIRLINK_ADMIN_SECRET")
    if not base or not secret:
        raise RuntimeError("AIRLINK_BASE_URL / AIRLINK_ADMIN_SECRET mancanti nelle env")

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

    r = requests.post(url, json=payload, headers=headers, timeout=20)
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"AirLink error {r.status_code}: {detail}")
    return r.json() if r.content else {}


def _get_active_partner_by_code(db: Session, referral_code: Optional[str]) -> Optional[Partner]:
    if not referral_code:
        return None
    return (
        db.query(Partner)
        .filter(Partner.referral_code == referral_code, Partner.is_active == True)  # noqa
        .first()
    )


def _calc_partner_discount(subtotal: Decimal, partner: Optional[Partner]) -> Decimal:
    if not partner:
        return Decimal("0.00")
    return money2((subtotal * PARTNER_DISCOUNT_PCT) / Decimal("100"))


def _product_label_for_email(order: Order, max_guests: Optional[int]) -> str:
    if order.order_type == OrderType.SINGLE:
        mg = max_guests or 0
        return f"SINGLE_{mg}"
    if order.order_type == OrderType.PACKAGE_TO:
        return f"PACKAGE_TO_{order.quantity}"
    if order.order_type == OrderType.PACKAGE_SCHOOL:
        return f"PACKAGE_SCHOOL_{order.quantity}"
    return str(order.order_type.value)


def fulfill_paid_order(db: Session, order: Order) -> dict[str, Any]:
    """
    Fulfillment idempotente:
    - se esistono già licenze per order_id -> non rigenerare (webhook può arrivare più volte)
    - crea licenza/e su AirLink
    - salva license/e su DB Site
    - invia email Payment confirmed (con primo codice)
    """
    if order.payment_status != PaymentStatus.PAID:
        raise RuntimeError("Order is not PAID. Refusing fulfillment.")

    # idempotenza: se già create licenze, non rigenerare
    existing = db.query(License).filter(License.order_id == order.id).all()
    if existing:
        first_code = existing[0].code if existing else None
        try:
            send_payment_received_email(
                to_email=order.buyer_email,
                order_id=order.id,
                product=None,
                license_code=first_code,
            )
        except Exception:
            pass
        return {"ok": True, "status": "already_fulfilled", "licenses": [x.code for x in existing]}

    partner = _get_active_partner_by_code(db, order.referral_code)

    # calcolo prezzi + parametri licenza
    max_guests: Optional[int] = None
    license_type = LicenseType.SINGLE

    if order.order_type == OrderType.SINGLE:
        # 🔥 convenzione: per SINGLE usiamo package_id come max_guests
        max_guests = int(order.package_id or 0)
        if max_guests not in LICENSE_PRICES:
            raise RuntimeError("Missing/invalid max_guests on order (package_id).")
        subtotal = money2(LICENSE_PRICES[max_guests] * Decimal(order.quantity or 1))
        est_cost = estimate_agora_cost_for_single_license(max_guests)
        license_type = LicenseType.SINGLE

    elif order.order_type == OrderType.PACKAGE_TO:
        if order.quantity not in TO_PACKAGES:
            raise RuntimeError("Invalid bundle_size for PACKAGE_TO.")
        subtotal = money2(TO_PACKAGES[int(order.quantity)])
        max_guests = 25
        est_cost = estimate_agora_cost_for_package(int(order.quantity), max_guests)
        license_type = LicenseType.TO

    elif order.order_type == OrderType.PACKAGE_SCHOOL:
        if order.quantity not in SCHOOL_PACKAGES:
            raise RuntimeError("Invalid bundle_size for PACKAGE_SCHOOL.")
        subtotal = money2(SCHOOL_PACKAGES[int(order.quantity)])
        max_guests = 100
        est_cost = estimate_agora_cost_for_package(int(order.quantity), max_guests)
        license_type = LicenseType.SCHOOL

    else:
        raise RuntimeError(f"Unsupported order_type: {order.order_type}")

    discount = _calc_partner_discount(subtotal, partner)
    total = money2(subtotal - discount)

    # aggiorna order breakdown (così admin vede importi veri)
    order.subtotal_amount = subtotal
    order.discount_amount = discount
    order.total_amount = total
    order.estimated_agora_cost = est_cost
    if partner:
        order.partner_id = partner.id

    # partner payout (se partner)
    if partner:
        try:
            payout_amount = money2((total * Decimal(str(partner.commission_pct))) / Decimal("100"))
            payout = PartnerPayout(
                partner_id=partner.id,
                order_id=order.id,
                amount=payout_amount,
                paid=False,
            )
            db.add(payout)
        except Exception:
            pass

    # crea licenze
    created_codes: list[str] = []
    for _ in range(int(order.quantity or 1)):
        code = generate_license_code()

        # AirLink first
        _airlink_create_license(
            code=code,
            max_listeners=int(max_guests or 0),
            duration_minutes=STANDARD_TOUR_MINUTES,
        )

        lic = License(
            code=code,
            license_type=license_type,
            max_guests=int(max_guests or 0),
            order_id=order.id,
        )
        db.add(lic)
        created_codes.append(code)

    db.add(order)
    db.commit()
    db.refresh(order)

    # email payment confirmed (con primo codice)
    try:
        send_payment_received_email(
            to_email=order.buyer_email,
            order_id=order.id,
            product=_product_label_for_email(order, max_guests),
            license_code=(created_codes[0] if created_codes else None),
        )
    except Exception:
        pass

    return {"ok": True, "status": "fulfilled", "licenses": created_codes}
