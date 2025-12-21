# routers/admin_partners.py

from typing import List, Optional
from decimal import Decimal
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from routers.auth_admin import get_current_admin
from schemas.partners import PartnerCreate, PartnerOut
from models.partners import Partner, PartnerType

router = APIRouter(
    prefix="/admin/partners",
    tags=["Admin Partners"],
)

logger = logging.getLogger(__name__)

# -------------------------------------------------
# TIER → COMMISSION DEFAULT
# -------------------------------------------------
TIER_DEFAULT_COMMISSION: dict[str, Decimal] = {
    "BASE": Decimal("10.0"),
    "PRO": Decimal("15.0"),
    "ELITE": Decimal("20.0"),
}


def normalize_tier(val: str | None) -> str:
    if not val:
        return "BASE"
    v = str(val).strip().upper()
    return v if v in TIER_DEFAULT_COMMISSION else "BASE"


def parse_bool(val: str | None) -> Optional[bool]:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s == "":
        return None
    if s in ("true", "1", "yes", "y", "on"):
        return True
    if s in ("false", "0", "no", "n", "off"):
        return False
    return None


# ---------------------------------------------------------
# ✅ NEW: COUNT PARTNER (SOLO ADMIN)
# ---------------------------------------------------------
@router.get("/count")
def admin_count_partners(
    active: Optional[str] = Query(default=None, description="true/false (anche 1/0, yes/no)"),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Ritorna un conteggio stabile (COUNT(*) sul DB).
    Se active=true  -> count is_active=True
    Se active=false -> count is_active=False
    Se active assente -> count totale
    """
    q = db.query(func.count(Partner.id))

    active_bool = parse_bool(active)
    if active_bool is True:
        q = q.filter(Partner.is_active.is_(True))
    elif active_bool is False:
        q = q.filter(Partner.is_active.is_(False))

    count = q.scalar() or 0
    return {"count": int(count)}


# ---------------------------------------------------------
# 1️⃣ LISTA COMPLETA PARTNER (SOLO ADMIN)
# ---------------------------------------------------------
@router.get("/", response_model=List[PartnerOut])
def admin_list_partners(
    active: Optional[str] = Query(default=None, description="true/false per filtrare is_active"),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Lista partner. (Lasciamo anche questo per la pagina /admin/partners)
    """
    q = db.query(Partner).order_by(Partner.created_at.desc())

    active_bool = parse_bool(active)
    if active_bool is True:
        q = q.filter(Partner.is_active.is_(True))
    elif active_bool is False:
        q = q.filter(Partner.is_active.is_(False))

    return q.all()


# ---------------------------------------------------------
# 2️⃣ DETTAGLIO SINGOLO PARTNER (SOLO ADMIN)
# ---------------------------------------------------------
@router.get("/{partner_id}", response_model=PartnerOut)
def admin_get_partner_detail(
    partner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner non trovato.",
        )
    return partner


# ---------------------------------------------------------
# 3️⃣ CREA UN NUOVO PARTNER (SOLO ADMIN)
# ---------------------------------------------------------
@router.post("/create", response_model=PartnerOut, status_code=status.HTTP_201_CREATED)
def admin_create_partner(
    payload: PartnerCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    existing_email = db.query(Partner).filter(Partner.email == payload.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email già registrata come partner.")

    existing_ref = db.query(Partner).filter(Partner.referral_code == payload.referral_code).first()
    if existing_ref:
        raise HTTPException(status_code=400, detail="Referral code già in uso.")

    try:
        partner_type = PartnerType(payload.partner_type.upper())
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="partner_type deve essere BASE, PRO o ELITE.",
        )

    partner = Partner(
        name=payload.name,
        email=payload.email,
        partner_type=partner_type,
        commission_pct=payload.commission_pct,
        referral_code=payload.referral_code,
        notes=payload.notes,
        is_active=True,
    )

    db.add(partner)
    db.commit()
    db.refresh(partner)

    return partner


# ---------------------------------------------------------
# 4️⃣ PROMUOVI / DECLASSA PARTNER (SOLO ADMIN)
# ---------------------------------------------------------
@router.patch("/{partner_id}/tier", response_model=PartnerOut)
def admin_set_partner_tier(
    partner_id: int,
    tier: str = Query(..., description="BASE|PRO|ELITE"),
    commission_pct: Decimal | None = Query(default=None, description="Override 0-100 (opzionale)"),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner non trovato.")

    chosen_tier = normalize_tier(tier)
    default_comm = TIER_DEFAULT_COMMISSION[chosen_tier]
    final_comm = commission_pct if commission_pct is not None else default_comm

    if final_comm < Decimal("0") or final_comm > Decimal("100"):
        raise HTTPException(status_code=400, detail="commission_pct deve essere tra 0 e 100.")

    old_tier = partner.partner_type.value if hasattr(partner.partner_type, "value") else str(partner.partner_type)

    partner.partner_type = PartnerType(chosen_tier)
    partner.commission_pct = final_comm

    db.add(partner)
    db.commit()
    db.refresh(partner)

    try:
        from app.email_service import send_partner_tier_changed_email
        send_partner_tier_changed_email(
            to_email=partner.email,
            partner_name=partner.name,
            old_tier=old_tier,
            new_tier=chosen_tier,
            commission_pct=str(final_comm),
        )
    except Exception as e:
        logger.warning("Email tier change fallita partner_id=%s: %s", partner_id, str(e))

    return partner


# ---------------------------------------------------------
# 5️⃣ ATTIVA / DISATTIVA COLLABORAZIONE (SOLO ADMIN)
# ---------------------------------------------------------
@router.patch("/{partner_id}/active", response_model=PartnerOut)
def admin_set_partner_active(
    partner_id: int,
    is_active: bool = Query(...),
    reason: str | None = Query(default=None),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner non trovato.")

    partner.is_active = bool(is_active)
    db.add(partner)
    db.commit()
    db.refresh(partner)

    if not is_active:
        try:
            from app.email_service import send_partner_collaboration_closed_email
            send_partner_collaboration_closed_email(
                to_email=partner.email,
                partner_name=partner.name,
                reason=reason or "",
            )
        except Exception as e:
            logger.warning("Email chiusura collaborazione fallita partner_id=%s: %s", partner_id, str(e))

    return partner


# ---------------------------------------------------------
# 6️⃣ DELETE PARTNER (SOLO ADMIN) - USARE CON CAUTELA
# ---------------------------------------------------------
@router.delete("/{partner_id}")
def admin_delete_partner(
    partner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner non trovato.")

    db.delete(partner)
    db.commit()
    return {"ok": True}
