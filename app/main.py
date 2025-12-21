from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import os

from dotenv import load_dotenv

# ----------------------------------------------------
# 🔐 LOAD .ENV (locale / Railway)
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

# ----------------------------------------------------
# 🚀 FASTAPI APP
# ----------------------------------------------------
app = FastAPI(
    title="VoiceGuide Backend Sito",
    version="1.0.0",
)

# ----------------------------------------------------
# 🌐 CORS CONFIG (DEV + PRODUZIONE)
# ----------------------------------------------------
# ✅ Lista base "hard" (non dipende da ENV)
base_origins = [
    # DEV
    "http://localhost:5173",
    "http://127.0.0.1:5173",

    # WEBAPP ADMIN / PARTNER
    "https://voiceguide-admin-production.up.railway.app",
    "https://voiceguide-partner-production.up.railway.app",

    # 🌍 SITO PUBBLICO
    "https://www.voiceguideapp.com",
    "https://voiceguideapp.com",
]

# ✅ Se su Railway esiste CORS_ORIGINS, NON deve distruggere la base:
# la uniamo alla lista base (merge).
cors_env = os.getenv("CORS_ORIGINS", "").strip()
env_origins = [o.strip() for o in cors_env.split(",") if o.strip()] if cors_env else []

# merge + dedup
origins = list(dict.fromkeys([*base_origins, *env_origins]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# 🛡️ OPTIONS CATCH-ALL (preflight "a prova di tutto")
# ----------------------------------------------------
# Questo elimina i casi in cui un proxy / router / setup causa 405 sul preflight.
@app.options("/{path:path}", include_in_schema=False)
async def options_handler(request: Request, path: str):
    origin = request.headers.get("origin")

    # Se l'origin è in allowlist, lo riecheggiamo (necessario con credentials).
    # Altrimenti non lo mettiamo (così non "apriamo" tutto al mondo).
    headers = {
        "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": request.headers.get(
            "access-control-request-headers", "Authorization,Content-Type"
        ),
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }
    if origin and origin in origins:
        headers["Access-Control-Allow-Origin"] = origin

    return Response(status_code=200, headers=headers)

# ----------------------------------------------------
# 🗄️ DB INIT (SOLO DEV)
# ⚠️ In produzione usare SOLO Alembic
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

# ----------------------------------------------------
# 🏠 ENDPOINTS BASE
# ----------------------------------------------------
@app.get("/")
def root():
    return {"message": "Backend VoiceGuide Sito attivo e pronto!"}

@app.get("/health")
def health():
    return {"ok": True}
