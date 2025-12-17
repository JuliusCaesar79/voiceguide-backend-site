# schemas/admin.py

from pydantic import BaseModel, EmailStr


# ------------------------
# Schema per LOGIN ADMIN
# ------------------------
class AdminLogin(BaseModel):
    email: EmailStr
    password: str


# ------------------------
# Output Admin (per risposte API)
# ------------------------
class AdminOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    is_superadmin: bool

    class Config:
        # Pydantic v2: sostituisce orm_mode = True
        from_attributes = True


# ------------------------
# Creazione Admin (opzionale per bootstrap)
# ------------------------
class AdminCreate(BaseModel):
    email: EmailStr
    password: str
    is_superadmin: bool = False
