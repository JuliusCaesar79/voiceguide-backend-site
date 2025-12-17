# routers/auth_admin.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db import get_db
from models.admin import Admin
from schemas.admin import AdminLogin, AdminOut
from app.security import create_access_token, decode_access_token

# ✅ bcrypt verify (no passlib)
from app.passwords import verify_password

router = APIRouter(prefix="/admin", tags=["Admin Auth"])

# Schema di sicurezza HTTP Bearer per gli admin
admin_bearer_scheme = HTTPBearer()


# ------------------------------
# POST /admin/login → login admin
# ------------------------------
@router.post("/login")
def admin_login(payload: AdminLogin, db: Session = Depends(get_db)):
    # Cerchiamo l'admin per email e attivo
    admin = (
        db.query(Admin)
        .filter(
            Admin.email == payload.email,
            Admin.is_active == True,  # noqa: E712
        )
        .first()
    )

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali admin non valide (email).",
        )

    # ✅ verifica corretta: password in chiaro vs hash bcrypt
    if not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali admin non valide (password).",
        )

    # Creiamo un token JWT con sub speciale: "admin:<id>"
    subject = f"admin:{admin.id}"
    access_token = create_access_token({"sub": subject})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": AdminOut.model_validate(admin),
    }


# -------------------------------------------------
# Dependency: controlla che il token sia di un admin
# -------------------------------------------------
def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(admin_bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    Legge il token JWT dall'header Authorization: Bearer <token>,
    verifica che il 'sub' inizi con 'admin:' e restituisce l'oggetto Admin.
    """
    token = credentials.credentials

    try:
        subject = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token admin non valido.",
        )

    # decode_access_token restituisce una stringa (sub)
    if not isinstance(subject, str) or not subject.startswith("admin:"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso negato: token non admin.",
        )

    # estraiamo l'ID numerico dopo "admin:"
    try:
        admin_id = int(subject.split(":", 1)[1])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token admin corrotto.",
        )

    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin non trovato.",
        )

    return admin
