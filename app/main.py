from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# ----------------------------------------------------
# 🔐 LOAD .ENV
# ----------------------------------------------------
load_dotenv(override=True)

from app.db import engine
from models import Base

# Routers
from routers import purchase, partners, auth_partner, partner_me
from routers import auth_admin, admin, payouts_admin, admin_partners
from routers import partner_portal, partner_payments_admin, admin_licenses
from routers import trial_requests, admin_trial_requests
from routers import admin_partner_requests, partner_requests
from routers import checkout
from routers import stripe_webhook  # ✅ NEW

# ----------------------------------------------------
# 🚀 FASTAPI APP
# ----------------------------------------------------
app = FastAPI(
    title="VoiceGuide Backend Sito",
    version="1.0.0",
)

# ----------------------------------------------------
# 🌐 CORS CONFIG
# ----------------------------------------------------
cors_env = os.getenv(
    "CORS_ORIGINS",
    ",".join([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://www.voiceguideapp.com",
        "https://voiceguideapp.com",
        "https://voiceguide-admin-production.up.railway.app",
        "https://voiceguide-partner-production.up.railway.app",
    ])
)

origins = [o.strip() for o in cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# 🟢 GLOBAL OPTIONS HANDLER (FIX DEFINITIVO)
# ----------------------------------------------------
@app.options("/{path:path}")
async def options_handler(path: str, request: Request):
    return Response(status_code=204)

# ----------------------------------------------------
# 🗄️ DB INIT (SOLO DEV)
# ----------------------------------------------------
if os.getenv("ENV", "dev") == "dev" and os.getenv("DB_AUTO_CREATE") == "1":
    Base.metadata.create_all(bind=engine)

# ----------------------------------------------------
# 🔌 ROUTERS
# ----------------------------------------------------
app.include_router(purchase.router)
app.include_router(partners.router)
app.include_router(auth_partner.router)
app.include_router(partner_me.router)

app.include_router(auth_admin.router)
app.include_router(admin.router)
app.include_router(payouts_admin.router)
app.include_router(admin_partners.router)

app.include_router(partner_portal.router)
app.include_router(partner_payments_admin.router)
app.include_router(admin_licenses.router)

app.include_router(trial_requests.router)
app.include_router(admin_trial_requests.router)

app.include_router(admin_partner_requests.router)
app.include_router(partner_requests.router)

app.include_router(checkout.router)

app.include_router(stripe_webhook.router)  # ✅ NEW (webhooks)

# ----------------------------------------------------
# 🏠 BASE
# ----------------------------------------------------
@app.get("/")
def root():
    return {"message": "Backend VoiceGuide Sito attivo e pronto!"}

@app.get("/health")
def health():
    return {"ok": True}
