# routers/admin_partners.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from routers.auth_admin import get_current_admin
from schemas.partners import PartnerCreate, PartnerOut
from models.partners import Partner, PartnerType

router = APIRouter(
    prefix="/admin/partners",
    tags=["Admin Partners"],
)

# ---------------------------------------------------------
# 1️⃣ LISTA COMPLETA PARTNER (SOLO ADMIN)
# ---------------------------------------------------------
@router.get("/", response_model=List[PartnerOut])
def admin_list_partners(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Restituisce la lista di tutti i partner registrati.
    Usato dalla pagina React /admin/partners.
    """
    partners = (
        db.query(Partner)
        .order_by(Partner.created_at.desc())
        .all()
    )
    return partners


# ---------------------------------------------------------
# 2️⃣ DETTAGLIO SINGOLO PARTNER (SOLO ADMIN)
# ---------------------------------------------------------
@router.get("/{partner_id}", response_model=PartnerOut)
def admin_get_partner_detail(
    partner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Restituisce il dettaglio di un singolo partner.
    Usato dalla pagina React /admin/partners/{id}.
    """
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
    """
    Crea un nuovo partner tramite pannello admin.
    Stessa logica di /partners/create, ma protetta da login admin.
    """

    # Controllo email duplicata
    existing_email = db.query(Partner).filter(Partner.email == payload.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email già registrata come partner.")

    # Controllo referral duplicato
    existing_ref = (
        db.query(Partner)
        .filter(Partner.referral_code == payload.referral_code)
        .first()
    )
    if existing_ref:
        raise HTTPException(
            status_code=400,
            detail="Referral code già in uso.",
        )

    # Conversione partner type (BASE, PRO, ELITE)
    try:
        partner_type = PartnerType(payload.partner_type.upper())
    except ValueError:
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
