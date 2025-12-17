from pydantic import BaseModel, EmailStr


class PartnerLoginRequest(BaseModel):
    email: EmailStr
    referral_code: str  # login doppio fattore semplice


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
