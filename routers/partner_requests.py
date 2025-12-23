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


def _extract_public_notes(payload: dict, parsed_public: PartnerRequestPublicIn) -> Optional[str]:
    """
    Estrae in modo robusto il messaggio del form pubblico.
    Supporta più chiavi possibili (perché il sito potrebbe inviare nomi diversi).
    """
    raw_msg = (
        parsed_public.message
        or payload.get("notes")
        or payload.get("messaggio")
        or payload.get("msg")
        or payload.get("text")
        or payload.get("body")
    )

    if isinstance(raw_msg, str):
        raw_msg = raw_msg.strip()
        return raw_msg if raw_msg else None

    return None


# ---------------------------------------------------------
# POST /partner-requests
# Accetta sia:
# - PartnerRequestCreate (interno)
# - PartnerRequestPublicIn (sito)
# ---------------------------------------------------------
@router.post("", response_model=PartnerRequestOut)
def create_partner_request(payload: dict, db: Session = Depends(get_db)):
    """
    ⚠️ Riceviamo dict per supportare 2 shape diverse.
    Poi proviamo a validare:
    1) schema interno PartnerRequestCreate
    2) schema pubblico PartnerRequestPublicIn
    """
    parsed_internal: Optional[PartnerRequestCreate] = None
    parsed_public: Optional[PartnerRequestPublicIn] = None

    # 1) Prova schema interno (quello che già usavi)
    try:
        parsed_internal = PartnerRequestCreate.model_validate(payload)
    except Exception:
        parsed_internal = None

    # 2) Prova schema pubblico (sito)
    if parsed_internal is None:
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
    if parsed_internal:
        name = parsed_internal.name.strip()
        email = str(parsed_internal.email).lower().strip()
        partner_tier = parsed_internal.partner_tier.value  # enum -> string
        notes = parsed_internal.notes.strip() if parsed_internal.notes else None
    else:
        name = parsed_public.name.strip()
        email = str(parsed_public.email).lower().strip()

        # organization -> partner_tier
        partner_tier = _tier_from_organization(parsed_public.organization)

        # message (o varianti) -> notes
        notes = _extract_public_notes(payload, parsed_public)

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
