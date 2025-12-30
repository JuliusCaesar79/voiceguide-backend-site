# app/fulfillment_service.py

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import os
import uuid
import logging
from typing import Any, Optional

import requests
from sqlalchemy.orm import Session

from models.orders import Order, OrderType, PaymentStatus
from models.licenses import License, LicenseType
from models.partners import Partner
from models.partner_payouts import PartnerPayout
from models.packages import Package  # ✅

from app.email_service import send_payment_received_email

logger = logging.getLogger(__name__)

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


def estimate_agora_cost_for_n_licenses(n: int, max_guests_per_license: int) -> Decimal:
    per_license = estimate_agora_cost_for_single_license(max_guests_per_license)
    return money2(per_license * Decimal(n))


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


def _product_label_for_email(order: Order, package: Optional[Package]) -> str:
    if order.order_type == OrderType.SINGLE:
        mg = int(package.max_guests) if package else 0
        return f"SINGLE_{mg}"
    if order.order_type == OrderType.PACKAGE_TO:
        nl = int(package.num_licenses) if package else int(order.quantity or 0)
        return f"PACKAGE_TO_{nl}"
    if order.order_type == OrderType.PACKAGE_SCHOOL:
        nl = int(package.num_licenses) if package else int(order.quantity or 0)
        return f"PACKAGE_SCHOOL_{nl}"
    return str(order.order_type.value)


def _load_package(db: Session, order: Order) -> Package:
    if not order.package_id:
        raise RuntimeError("Order missing package_id.")
    pkg = db.query(Package).filter(Package.id == int(order.package_id)).first()
    if not pkg:
        raise RuntimeError(f"Package not found for package_id={order.package_id}")
    if hasattr(pkg, "is_active") and pkg.is_active is False:
        raise RuntimeError("Package is not active.")
    return pkg


def _safe_send_payment_email(*, to_email: str, order_id: int, product: Optional[str], license_code: Optional[str]) -> None:
    """
    Wrapper: LOGGA SEMPRE l'invio email, e logga l'eccezione se fallisce.
    Così su Railway vediamo finalmente cosa succede.
    """
    try:
        logger.info(
            "EMAIL: attempting send_payment_received_email | to=%s | order_id=%s | product=%s | license_code=%s",
            to_email,
            order_id,
            product,
            license_code,
        )
        send_payment_received_email(
            to_email=to_email,
            order_id=order_id,
            product=product,
            license_code=license_code,
        )
        logger.info("EMAIL: send_payment_received_email DONE | to=%s | order_id=%s", to_email, order_id)
    except Exception:
        logger.exception("EMAIL: send_payment_received_email FAILED | to=%s | order_id=%s", to_email, order_id)


def fulfill_paid_order(
    *,
    db: Session,
    order: Order,
    stripe_session: Optional[dict[str, Any]] = None,  # ✅ accetta stripe_session
) -> dict[str, Any]:
    """
    Fulfillment idempotente:
    - se esistono già licenze per order_id -> non rigenerare (webhook può arrivare più volte)
    - crea licenza/e su AirLink
    - salva license/e su DB Site
    - invia email Payment confirmed (con primo codice)
    """
    if order.payment_status != PaymentStatus.PAID:
        raise RuntimeError("Order is not PAID. Refusing fulfillment.")

    # idempotenza
    existing = db.query(License).filter(License.order_id == order.id).order_by(License.id.asc()).all()
    if existing:
        first_code = existing[0].code if existing else None

        # ✅ ora logghiamo sempre
        _safe_send_payment_email(
            to_email=order.buyer_email,
            order_id=order.id,
            product=None,
            license_code=first_code,
        )

        return {"ok": True, "status": "already_fulfilled", "licenses": [x.code for x in existing]}

    partner = _get_active_partner_by_code(db, order.referral_code)

    # ✅ usa la tabella packages (FK)
    pkg = _load_package(db, order)

    # mapping license_type
    if order.order_type == OrderType.SINGLE:
        license_type = LicenseType.SINGLE
    elif order.order_type == OrderType.PACKAGE_TO:
        license_type = LicenseType.TO
    elif order.order_type == OrderType.PACKAGE_SCHOOL:
        license_type = LicenseType.SCHOOL
    else:
        raise RuntimeError(f"Unsupported order_type: {order.order_type}")

    max_guests = int(pkg.max_guests or 0)
    num_licenses_per_unit = int(pkg.num_licenses or 1)
    units = int(order.quantity or 1)

    total_licenses_to_create = units * num_licenses_per_unit

    # prezzi + costi
    subtotal = money2(Decimal(str(pkg.price)) * Decimal(units))
    discount = _calc_partner_discount(subtotal, partner)
    total = money2(subtotal - discount)

    est_cost = estimate_agora_cost_for_n_licenses(total_licenses_to_create, max_guests)

    # aggiorna breakdown ordine
    order.subtotal_amount = subtotal
    order.discount_amount = discount
    order.total_amount = total
    order.estimated_agora_cost = est_cost
    if partner:
        order.partner_id = partner.id

    # partner payout
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
            logger.exception("Partner payout creation failed for order_id=%s partner_id=%s", order.id, partner.id)

    # crea licenze
    created_codes: list[str] = []
    for _ in range(total_licenses_to_create):
        code = generate_license_code()

        _airlink_create_license(
            code=code,
            max_listeners=max_guests,
            duration_minutes=STANDARD_TOUR_MINUTES,
        )

        lic = License(
            code=code,
            license_type=license_type,
            max_guests=max_guests,
            order_id=order.id,
        )
        db.add(lic)
        created_codes.append(code)

    db.add(order)
    db.commit()
    db.refresh(order)

    # ✅ email (primo codice) - ora con log visibile su Railway
    _safe_send_payment_email(
        to_email=order.buyer_email,
        order_id=order.id,
        product=_product_label_for_email(order, pkg),
        license_code=(created_codes[0] if created_codes else None),
    )

    return {"ok": True, "status": "fulfilled", "licenses": created_codes}
