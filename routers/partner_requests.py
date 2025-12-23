# routers/partner_requests.py

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from models.partner_requests import PartnerRequest, PartnerRequestStatus
from schemas.partner_requests import PartnerRequestCreate, PartnerRequestOut

router = APIRouter(prefix="/partner-requests", tags=["Partner Requests"])


# ---------------------------------------------------------
# ✅ Payload "pubblico" dal sito (Vercel)
# ---------------------------------------------------------
class PartnerRequestPublicIn(BaseModel):
    name: str
    email: EmailStr
    organization: Optional[str] = None
    message: Optional[str] = None


def _tier_from_organization(org: Optional[str]) -> str:
    """
    Converte una stringa 'organization' in un tier valido per DB.
    Se non riconosciamo, mettiamo BASE.
    """
    if not org:
        return "BASE"

    v = org.strip().lower()

    # euristiche: personalizzabili
    if "elite" in v or "enterprise" in v:
        return "ELITE"
    if (
        "pro" in v
        or "agen" in v
        or "agency" in v
        or "tour operator" in v
        or v in {"to", "tour"}
    ):
        return "PRO"

    return "BASE"


def _looks_like_public(payload: dict) -> bool:
    """
    Decide se il payload arriva dal sito (public form) o dal flusso interno.
    Il problema che stai vedendo nasce quando il modello interno "accetta"
    campi extra e quindi 'message' viene ignorato.
    """
    keys = set(payload.keys())
    # se vedo organization/message, è quasi sicuramente il form del sito
    if "organization" in keys or "message" in keys:
        return True
    # se NON vedo partner_tier/notes ma vedo name+email, trattalo come public
    if ("partner_tier" not in keys and "notes" not in keys) and (
        "name" in keys and "email" in keys
    ):
        return True
    return False


# ---------------------------------------------------------
# POST /partner-requests
# Accetta sia:
# - PartnerRequestPublicIn (sito)  ✅ PRIORITÀ
# - PartnerRequestCreate (interno)
# ---------------------------------------------------------
@router.post("", response_model=PartnerRequestOut)
def create_partner_request(payload: dict, db: Session = Depends(get_db)):
    """
    Riceviamo dict per supportare 2 shape diverse.
    ✅ FIX: priorità al payload pubblico (per non perdere 'message').
    """
    parsed_internal: Optional[PartnerRequestCreate] = None
    parsed_public: Optional[PartnerRequestPublicIn] = None

    # 1) Se sembra "public", valida prima come public
    if _looks_like_public(payload):
        try:
            parsed_public = PartnerRequestPublicIn.model_validate(payload)
        except Exception:
            parsed_public = None

    # 2) Se non è public (o validazione fallita), prova interno
    if parsed_public is None:
        try:
            parsed_internal = PartnerRequestCreate.model_validate(payload)
        except Exception:
            parsed_internal = None

    # 3) Se ancora nulla, ultimo tentativo: prova public anche se non "sembra" public
    if parsed_internal is None and parsed_public is None:
        try:
            parsed_public = PartnerRequestPublicIn.model_validate(payload)
        except Exception:
            parsed_public = None

    if parsed_internal is None and parsed_public is None:
        raise HTTPException(
            status_code=422,
            detail="Invalid payload. Expected PartnerRequestCreate or public partner form payload.",
        )

    # Normalizziamo campi comuni
    if parsed_public is not None:
        name = parsed_public.name.strip()
        email = str(parsed_public.email).lower().strip()

        # organization -> partner_tier
        partner_tier = _tier_from_organization(parsed_public.organization)

        # message -> notes
        notes = parsed_public.message.strip() if parsed_public.message else None
    else:
        name = parsed_internal.name.strip()
        email = str(parsed_internal.email).lower().strip()
        partner_tier = parsed_internal.partner_tier.value  # enum -> string
        notes = parsed_internal.notes.strip() if parsed_internal.notes else None

    if not name:
        raise HTTPException(status_code=422, detail="Missing field: name")
    if not email:
        raise HTTPException(status_code=422, detail="Missing field: email")

    # Anti-duplicati applicativo (se già pending)
    existing = (
        db.query(PartnerRequest)
        .filter(
            PartnerRequest.email == email,
            PartnerRequest.status == PartnerRequestStatus.PENDING,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A request for this email is already pending.",
        )

    req = PartnerRequest(
        name=name,
        email=email,
        partner_tier=partner_tier,  # string coerente col DB ENUM
        notes=notes,
        status=PartnerRequestStatus.PENDING,
    )

    db.add(req)

    # ✅ Gestione robusta del vincolo UNIQUE su email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A request for this email already exists.",
        )

    db.refresh(req)
    return req
