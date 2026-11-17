# routers/app_licenses.py
"""
"Le mie licenze" nell'app VoiceGuide AirLink (Fase 1, 2026-11-18).

GET /api/app/my-licenses
  Header: Authorization: Bearer <access token Supabase dell'app>

L'account dell'app vive su Supabase (progetto `itinerarium`). Qui il token
viene verificato chiedendo a Supabase chi è l'utente (/auth/v1/user): solo
così si ottiene un'email affidabile, già confermata col codice o con Google.
Si restituiscono le licenze legate a quell'email:
  - acquistate sul sito (orders.buyer_email, ordini pagati);
  - mandate a mano, prove e 3 tour gratuiti (licenses.issued_to_email).
Lo stato d'uso (nuova / in corso / usata) è letto da AirLink, che è il
backend che le attiva davvero.
"""
import logging
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from models.licenses import License
from models.orders import Order, PaymentStatus
from routers.admin_licenses import _env

router = APIRouter(prefix="/api/app", tags=["App - Le mie licenze"])
logger = logging.getLogger(__name__)

# Valori pubblici (sono già dentro l'app): si possono sovrascrivere da env.
DEFAULT_SUPABASE_URL = "https://dtbcfjsqwhmdfwkxighr.supabase.co"
DEFAULT_SUPABASE_ANON_KEY = "sb_publishable_6y-VAzI3BJtZe5c9QrEB5w_h18N4DTY"


def _supabase_email(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    base = _env("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")
    key = _env("SUPABASE_ANON_KEY", DEFAULT_SUPABASE_ANON_KEY)
    try:
        r = requests.get(
            f"{base}/auth/v1/user",
            headers={"apikey": key, "Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except Exception as e:
        logger.warning("my-licenses: Supabase non raggiungibile: %s", e)
        raise HTTPException(status_code=503, detail="Auth unavailable")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = r.json() or {}
    email = (user.get("email") or "").strip().lower()
    if not email or not user.get("email_confirmed_at"):
        raise HTTPException(status_code=401, detail="Email not confirmed")
    return email


def _airlink_status(codes: list[str]) -> dict[str, dict] | None:
    """{codice: {activated_at, is_active}} da AirLink; None se non risponde."""
    base, secret = _env("AIRLINK_BASE_URL"), _env("AIRLINK_ADMIN_SECRET")
    if not codes:
        return {}
    if not base or not secret:
        return None
    try:
        r = requests.post(
            f"{base.rstrip('/')}/api/admin/licenses/status",
            json={"codes": codes},
            headers={"X-Admin-Secret": secret},
            timeout=10,
        )
        r.raise_for_status()
        return {i["code"]: i for i in r.json().get("items", [])}
    except Exception as e:
        logger.warning("my-licenses: stato AirLink non disponibile: %s", e)
        return None


def _parse_dt(v) -> datetime | None:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _source(lic: License) -> str:
    """Da dove viene la licenza, senza esporre chi l'ha emessa."""
    if lic.order_id:
        return "order"
    if lic.issued_by_admin == "free_signup":
        return "free"
    if lic.issued_by_admin == "auto":
        return "trial"
    return "gift"


@router.get("/my-licenses")
def my_licenses(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    email = _supabase_email(authorization)

    paid_order_ids = (
        db.query(Order.id)
        .filter(func.lower(func.trim(Order.buyer_email)) == email)
        .filter(Order.payment_status == PaymentStatus.PAID)
    )
    licenses = (
        db.query(License)
        .filter(
            or_(
                func.lower(func.trim(License.issued_to_email)) == email,
                License.order_id.in_(paid_order_ids),
            )
        )
        .order_by(License.created_at.desc())
        .limit(300)
        .all()
    )

    status_map = _airlink_status([l.code for l in licenses])
    now = datetime.now(timezone.utc)
    items = []
    for lic in licenses:
        duration_h = int(lic.duration_hours or 4)
        if status_map is None:
            state, activated_at, expires_at = "unknown", None, None
        else:
            st = status_map.get(lic.code)
            activated_at = _parse_dt(st.get("activated_at")) if st else None
            expires_at = activated_at + timedelta(hours=duration_h) if activated_at else None
            if not st:
                state = "unknown"  # non ancora sincronizzata su AirLink
            elif activated_at is None:
                state = "new"
            elif st.get("is_active", True) and expires_at and expires_at > now:
                state = "active"
            else:
                state = "used"
        if not lic.is_active and state == "new":
            state = "revoked"
        items.append(
            {
                "code": lic.code,
                "type": lic.license_type.value if lic.license_type else None,
                "max_guests": lic.max_guests,
                "duration_hours": duration_h,
                "source": _source(lic),
                "created_at": lic.created_at.isoformat() if lic.created_at else None,
                "activated_at": activated_at.isoformat() if activated_at else None,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "state": state,
            }
        )

    counts = {s: sum(1 for i in items if i["state"] == s) for s in ("new", "active", "used")}
    return {"email": email, "items": items, "counts": counts}
