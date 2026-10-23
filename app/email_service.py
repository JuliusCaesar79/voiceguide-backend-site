# app/email_service.py
import os
import re
import smtplib
from email.message import EmailMessage
from html import escape

# 🔥 forza il caricamento del .env in locale (e non rompe in produzione)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


def _get_env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name, default)
    if v in ("", None):
        return default
    return v


DEFAULT_FROM_NAME = "VoiceGuide Team"

PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.voiceguideairlinkbare&pcampaignid=web_share"
APP_STORE_URL = "https://apps.apple.com/it/app/voiceguide-airlink/id6757807346"
PURCHASE_PAGE_URL = "https://www.voiceguideapp.com/en/licenze"
PARTNER_DISCOUNT_CODE = "VG-1F0DC4"
WHATSAPP_URL = "https://wa.me/393755908650"


def _friendly_product_label(product_code: str, language: str = "en") -> str:
    """
    Traduce un codice prodotto tecnico (es. SINGLE_25, PACKAGE_TO_10) in
    un'etichetta leggibile per il cliente. Se il codice non è riconosciuto,
    ritorna il codice originale così com'è (nessun dato perso).
    """
    code = (product_code or "").strip().upper()
    lang = (language or "en").strip().lower()

    m = re.fullmatch(r"SINGLE_(\d+)", code)
    if m:
        n = m.group(1)
        return f"Licenza Singola ({n} ospiti)" if lang == "it" else f"Single License ({n} guests)"

    m = re.fullmatch(r"PACKAGE_TO_(\d+)", code)
    if m:
        n = m.group(1)
        return f"Pacchetto Tour Operator ({n} licenze)" if lang == "it" else f"Tour Operator Package ({n} licenses)"

    m = re.fullmatch(r"PACKAGE_SCHOOL_(\d+)", code)
    if m:
        n = m.group(1)
        return f"Pacchetto Scuole ({n} licenze)" if lang == "it" else f"School Package ({n} licenses)"

    return product_code


def _send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """
    Invio email. headers: intestazioni extra (es. List-Unsubscribe).
    Provider selezionabile via env:
    - EMAIL_PROVIDER=resend  (consigliato in produzione)
    - EMAIL_PROVIDER=smtp    (fallback)
    Se EMAIL_ENABLED != "1" non fa nulla (safe per dev).
    """
    enabled = _get_env("EMAIL_ENABLED", "0")
    if enabled != "1":
        return

    provider = (_get_env("EMAIL_PROVIDER", "smtp") or "smtp").lower().strip()

    # ------------------------
    # RESEND (HTTP API)
    # ------------------------
    if provider == "resend":
        import requests  # richiede 'requests' in requirements

        api_key = _get_env("RESEND_API_KEY")
        from_email = _get_env("FROM_EMAIL") or _get_env("SMTP_FROM")  # fallback
        from_name = _get_env("FROM_NAME") or _get_env("SMTP_FROM_NAME") or DEFAULT_FROM_NAME
        reply_to = _get_env("REPLY_TO_EMAIL") or _get_env("SMTP_REPLY_TO")

        if not api_key or not from_email:
            raise RuntimeError("RESEND_API_KEY / FROM_EMAIL mancanti nelle variabili d'ambiente.")

        payload: dict = {
            "from": f"{from_name} <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "text": text_body,
        }
        if html_body:
            payload["html"] = html_body
        if reply_to:
            payload["reply_to"] = reply_to
        if headers:
            payload["headers"] = headers

        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )

        if r.status_code >= 300:
            raise RuntimeError(f"Resend send failed: {r.status_code} {r.text}")

        return

    # ------------------------
    # SMTP (fallback)
    # ------------------------
    host = _get_env("SMTP_HOST")
    port = int(_get_env("SMTP_PORT", "587") or "587")
    user = _get_env("SMTP_USER")
    password = _get_env("SMTP_PASS")
    from_email = _get_env("SMTP_FROM", user)
    from_name = _get_env("SMTP_FROM_NAME", DEFAULT_FROM_NAME)
    reply_to = _get_env("SMTP_REPLY_TO")
    use_tls = _get_env("SMTP_TLS", "1") == "1"

    # ✅ hardening: rimuove spazi accidentali
    if password:
        password = password.replace(" ", "").strip()

    if not host or not from_email:
        raise RuntimeError("SMTP_HOST/SMTP_FROM mancanti nelle variabili d'ambiente.")

    # Mittente "Nome <email>"
    from_header = f"{from_name} <{from_email}>" if from_name else from_email

    msg = EmailMessage()
    msg["From"] = from_header
    msg["To"] = to_email
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    for k, v in (headers or {}).items():
        msg[k] = v

    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.send_message(msg)


# ✅ Manteniamo la funzione esistente (compatibilità)
def send_receipt_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


# =================================================
# NEW: ORDER RECEIVED (PENDING) — per checkout “reale” senza Stripe/PayPal
# =================================================
def send_order_received_email(
    to_email: str,
    order_id: int,
    product: str,
    total_amount: float,
    discount_amount: float = 0.0,
    invoice_requested: bool = False,
    intestatario: str | None = None,
    language: str = "en",
) -> None:
    """Ordine ricevuto (pagamento in attesa): email nello stile nuovo, in 5 lingue."""
    from app.customer_emails import send_order_received

    send_order_received(
        to_email=to_email,
        order_id=order_id,
        product=product,
        total_amount=total_amount,
        discount_amount=discount_amount,
        invoice_requested=invoice_requested,
        intestatario=intestatario,
        language=language,
    )


# -------------------------------------------------
# PARTNER EMAILS (APPROVE / REJECT / TIER / CLOSE): in 5 lingue in app/partner_emails.py
# -------------------------------------------------
def send_partner_request_approved_email(
    to_email: str,
    referral_code: str,
    partner_name: str | None = None,
    commission_pct: str | None = None,
    tier: str | None = None,
    language: str | None = None,
) -> None:
    from app.partner_emails import send_partner_approved_email

    send_partner_approved_email(to_email, referral_code, partner_name, commission_pct, tier, language)


def send_partner_request_rejected_email(
    to_email: str,
    partner_name: str | None = None,
    language: str | None = None,
) -> None:
    from app.partner_emails import send_partner_rejected_email

    send_partner_rejected_email(to_email, partner_name, language)


def send_partner_tier_changed_email(
    to_email: str,
    partner_name: str | None = None,
    old_tier: str | None = None,
    new_tier: str | None = None,
    commission_pct: str | None = None,
    language: str | None = None,
) -> None:
    from app.partner_emails import send_partner_tier_email

    send_partner_tier_email(to_email, partner_name, old_tier, new_tier, commission_pct, language)


def send_partner_collaboration_closed_email(
    to_email: str,
    partner_name: str | None = None,
    reason: str | None = None,
    language: str | None = None,
) -> None:
    from app.partner_emails import send_partner_closed_email

    send_partner_closed_email(to_email, partner_name, reason, language)


# -------------------------------------------------
# TRIAL / MANUAL LICENSE EMAIL - ENGLISH
# -------------------------------------------------
def send_trial_license_email(
    to_email: str,
    license_code: str,
    max_guests: int,
    name: str | None = None,
    language: str = "en",
) -> None:
    """Licenza di prova: email nello stile nuovo, in 5 lingue."""
    from app.customer_emails import send_trial_license

    send_trial_license(to_email=to_email, license_code=license_code, max_guests=max_guests, name=name, language=language)


def send_payment_received_email(
    to_email: str,
    order_id: int,
    product: str | None = None,
    license_code: str | None = None,
    license_codes: list[str] | None = None,
    language: str | None = None,
) -> None:
    """
    Pagamento confermato con i codici licenza, nella lingua dell'ordine
    (orders.language; gli ordini vecchi senza lingua restano in inglese).
    Supporta sia un codice singolo (license_code) sia una lista (pacchetti).
    """
    from app.customer_emails import send_payment_confirmed

    codes: list[str] = []
    if license_codes:
        codes = [c.strip() for c in license_codes if (c or "").strip()]
    elif license_code and license_code.strip():
        codes = [license_code.strip()]

    send_payment_confirmed(to_email=to_email, order_id=order_id, product=product, codes=codes, language=language or "en")


