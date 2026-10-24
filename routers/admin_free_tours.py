# routers/admin_free_tours.py
"""
Dashboard admin: registrazioni con 3 tour gratuiti.

GET /admin/free-tours  → riepilogo + elenco dei registrati, con quanti dei
3 codici ognuno ha davvero attivato (stato letto da AirLink in una chiamata)
e se poi ha comprato (ordini pagati con la stessa email normalizzata).
"""
import logging
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.email_guard import normalize_email
from models.admin import Admin
from models.free_tour_signups import FreeTourSignup
from models.licenses import License
from models.orders import Order, PaymentStatus
from routers.admin_licenses import _env
from routers.auth_admin import get_current_admin
from routers.free_tours import ISSUED_BY

router = APIRouter(prefix="/admin", tags=["Admin - Free tours"])
logger = logging.getLogger(__name__)


def _airlink_activations(codes: list[str]) -> dict[str, str | None] | None:
    """{codice: activated_at} da AirLink; None se AirLink non risponde."""
    base, secret = _env("AIRLINK_BASE_URL"), _env("AIRLINK_ADMIN_SECRET")
    if not codes or not base or not secret:
        return {} if not codes else None
    try:
        r = requests.post(
            f"{base.rstrip('/')}/api/admin/licenses/status",
            json={"codes": codes},
            headers={"X-Admin-Secret": secret},
            timeout=10,
        )
        r.raise_for_status()
        return {i["code"]: i.get("activated_at") for i in r.json().get("items", [])}
    except Exception as e:
        logger.warning("Free tours admin: AirLink status non disponibile: %s", e)
        return None


@router.get("/free-tours")
def list_free_tours(
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    now = datetime.now(timezone.utc)

    signups = (
        db.query(FreeTourSignup)
        .filter(FreeTourSignup.verified_at.isnot(None))
        .order_by(FreeTourSignup.verified_at.desc())
        .limit(limit)
        .all()
    )
    pending = (
        db.query(FreeTourSignup.email_normalized)
        .filter(FreeTourSignup.verified_at.is_(None))
        .distinct()
        .count()
    )
    licenses = db.query(License).filter(License.issued_by_admin == ISSUED_BY).all()
    by_email: dict[str, list[License]] = {}
    for lic in licenses:
        by_email.setdefault(lic.issued_to_email or "", []).append(lic)

    activations = _airlink_activations([lic.code for lic in licenses])

    # Acquisti dei registrati: ordini pagati, email confrontata normalizzata
    paid_by_email: dict[str, list[Order]] = {}
    for o in db.query(Order).filter(Order.payment_status == PaymentStatus.PAID).all():
        paid_by_email.setdefault(normalize_email(o.buyer_email), []).append(o)

    def aware(d):
        return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)

    items = []
    used_total = 0
    for s in signups:
        lics = sorted(by_email.get(s.email_normalized, []), key=lambda x: x.max_guests)
        rows = []
        for lic in lics:
            act = activations.get(lic.code) if activations is not None else None
            used_total += 1 if act else 0
            rows.append({"code": lic.code, "max_guests": lic.max_guests, "activated_at": act})
        orders = paid_by_email.get(s.email_normalized, [])
        items.append(
            {
                "id": s.id,
                "email": s.email,
                "language": s.language,
                "registered_at": s.verified_at,
                "licenses": rows,
                "used": sum(1 for r in rows if r["activated_at"]),
                "orders_paid": len(orders),
                "spent": round(sum(float(o.total_amount or 0) for o in orders), 2),
            }
        )

    def since(days: int) -> int:
        limit_dt = now - timedelta(days=days)
        return sum(1 for s in signups if aware(s.verified_at) >= limit_dt)

    return {
        "summary": {
            "total": len(signups),
            "last_7_days": since(7),
            "last_30_days": since(30),
            "codes_sent_not_confirmed": pending,
            "tours_used": used_total,
            "registrants_who_used": sum(1 for i in items if i["used"] > 0),
            "registrants_who_bought": sum(1 for i in items if i["orders_paid"] > 0),
            "revenue_from_registrants": round(sum(i["spent"] for i in items), 2),
            "airlink_status_available": activations is not None,
        },
        "items": items,
    }
