# routers/auth_admin.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.db import get_db
from models.admin import Admin
from schemas.admin import AdminLogin, AdminOut
from app.security import create_access_token, decode_access_token

router = APIRouter(prefix="/admin", tags=["Admin Auth"])

admin_bearer_scheme = HTTPBearer()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login")
def admin_login(payload: AdminLogin, db: Session = Depends(get_db)):
    admin = (
        db.query(Admin)
        .filter(
            Admin.email == payload.email,
            Admin.is_active == True,  # noqa
        )
        .first()
    )

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali admin non valide (email).",
        )

    # ✅ VERIFICA BCRYPT CORRETTA
    if not pwd_context.verify(payload.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali admin non valide (password).",
        )

    subject = f"admin:{admin.id}"
    access_token = create_access_token({"sub": subject})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": AdminOut.model_validate(admin),
    }


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(admin_bearer_scheme),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    subject = decode_access_token(token)

    if not subject or not subject.startswith("admin:"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso negato: token non admin.",
        )

    admin_id = int(subject.split(":", 1)[1])
    admin = db.query(Admin).filter(Admin.id == admin_id).first()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin non trovato.",
        )

    return admin
