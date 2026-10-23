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
PARTNER_PORTAL_URL = "https://voiceguide-partner-production.up.railway.app"


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
) -> None:
    """
    Invio email.
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


def _branded(subject: str, html_body: str) -> str:
    """Mette il contenuto nel layout comune (logo, scheda, piè di pagina). Email partner: in inglese."""
    from app.email_layout import layout

    title = subject.split("—", 1)[-1].strip().rstrip("✅").strip()
    return layout(title, html_body, "en")


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
# PARTNER REQUEST EMAILS (APPROVE / REJECT) - ENGLISH
# -------------------------------------------------
def send_partner_request_approved_email(
    to_email: str,
    referral_code: str,
    partner_name: str | None = None,
    commission_pct: str | None = None,
    tier: str | None = None,
) -> None:
    name = (partner_name or "Partner").strip()
    safe_name = escape(name)
    safe_code = escape(referral_code)

    subject = "VoiceGuide — Partner Request Approved ✅"

    # TEXT (EN)
    lines = [
        f"Hello {name},",
        "",
        "We are pleased to inform you that your request to become a VoiceGuide Partner has been approved.",
        "",
        "Your Partner Code is:",
        f"{referral_code}",
    ]
    if tier:
        lines.append(f"Tier: {tier}")
    if commission_pct:
        lines.append(f"Commission: {commission_pct}%")
    lines += [
        "",
        "You can share this code with your clients during the purchase process.",
        "",
        "Log in to your Partner Dashboard to track your orders and commissions:",
        PARTNER_PORTAL_URL,
        "(use your email and the Partner Code above to log in)",
        "",
        "If you have any questions, simply reply to this email or reach us on WhatsApp:",
        WHATSAPP_URL,
        "",
        "Best regards,",
        "VoiceGuide Team",
    ]
    text_body = "\n".join(lines)

    # HTML (EN)
    html_extra = ""
    if tier or commission_pct:
        html_extra = "<p style='margin:0 0 12px 0;'>"
        if tier:
            html_extra += f"<b>Tier:</b> {escape(str(tier))}<br/>"
        if commission_pct:
            html_extra += f"<b>Commission:</b> {escape(str(commission_pct))}%"
        html_extra += "</p>"

    html_body = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
      <p>Hello <b>{safe_name}</b>,</p>

      <p>We are pleased to inform you that your request to become a <b>VoiceGuide Partner</b> has been approved.</p>

      <div style="padding:14px;border:1px solid #e5e5e5;border-radius:10px;margin:16px 0;">
        <div style="font-size:12px;color:#666;margin-bottom:6px;">Your Partner Code</div>
        <div style="font-size:22px;letter-spacing:1px;"><b>{safe_code}</b></div>
      </div>

      {html_extra}

      <p>You can share this code with your clients during the purchase process.</p>

      <div style="padding:14px;border:1px solid #FFC226;border-radius:10px;margin:16px 0;background:#FFFBEF;">
        <p style="margin:0 0 8px 0;">Log in to your Partner Dashboard to track your orders and commissions.</p>
        <p style="margin:0 0 8px 0;"><a href="{PARTNER_PORTAL_URL}"><b>Open Partner Dashboard →</b></a></p>
        <p style="margin:0;color:#666;font-size:13px;">(use your email and the Partner Code above to log in)</p>
      </div>

      <p>If you have any questions, simply reply to this email or reach us on <a href="{WHATSAPP_URL}">WhatsApp</a>.</p>

      <p style="margin-top:18px;color:#444;">Best regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=_branded(subject, html_body))


def send_partner_request_rejected_email(
    to_email: str,
    partner_name: str | None = None,
) -> None:
    name = (partner_name or "Partner").strip()
    safe_name = escape(name)

    subject = "VoiceGuide — Partner Request Update"

    # TEXT (EN)
    text_body = "\n".join(
        [
            f"Hello {name},",
            "",
            "Thank you for your interest in becoming a VoiceGuide Partner.",
            "",
            "After reviewing your request, we are unable to approve it at this time.",
            "",
            "If you would like further information or wish to submit a new request in the future, feel free to reply to this email or reach us on WhatsApp:",
            WHATSAPP_URL,
            "",
            "Kind regards,",
            "VoiceGuide Team",
        ]
    )

    # HTML (EN)
    html_body = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
      <p>Hello <b>{safe_name}</b>,</p>

      <p>Thank you for your interest in becoming a <b>VoiceGuide Partner</b>.</p>

      <p>After reviewing your request, we are unable to approve it at this time.</p>

      <p>If you would like further information or wish to submit a new request in the future, feel free to reply to this email or reach us on <a href="{WHATSAPP_URL}">WhatsApp</a>.</p>

      <p style="margin-top:18px;color:#444;">Kind regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=_branded(subject, html_body))


# -------------------------------------------------
# PARTNER ADMIN EMAILS (TIER CHANGE / COLLAB CLOSE) - ENGLISH
# -------------------------------------------------
def send_partner_tier_changed_email(
    to_email: str,
    partner_name: str | None = None,
    old_tier: str | None = None,
    new_tier: str | None = None,
    commission_pct: str | None = None,
) -> None:
    """
    Email inviata quando un admin cambia il tier del partner (promozione/declassamento).
    """
    name = (partner_name or "Partner").strip()
    safe_name = escape(name)
    safe_old = escape(str(old_tier or ""))
    safe_new = escape(str(new_tier or ""))
    safe_comm = escape(str(commission_pct or ""))

    subject = "VoiceGuide — Partner Tier Updated"

    # TEXT (EN)
    lines = [
        f"Hello {name},",
        "",
        "Your VoiceGuide Partner tier has been updated by our admin team.",
        "",
    ]
    if old_tier and new_tier:
        lines.append(f"Tier: {old_tier} → {new_tier}")
    elif new_tier:
        lines.append(f"New tier: {new_tier}")
    if commission_pct:
        lines.append(f"Commission: {commission_pct}%")
    lines += [
        "",
        "If you have any questions, simply reply to this email or reach us on WhatsApp:",
        WHATSAPP_URL,
        "",
        "Best regards,",
        "VoiceGuide Team",
    ]
    text_body = "\n".join(lines)

    # HTML (EN)
    html_body = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
      <p>Hello <b>{safe_name}</b>,</p>

      <p>Your <b>VoiceGuide Partner</b> tier has been updated by our admin team.</p>

      <div style="padding:14px;border:1px solid #e5e5e5;border-radius:10px;margin:16px 0;">
        <div style="font-size:12px;color:#666;margin-bottom:6px;">Update details</div>
        <div style="font-size:14px;">
          {"<b>Tier:</b> " + safe_old + " → " + safe_new + "<br/>" if (old_tier and new_tier) else ""}
          {"<b>New tier:</b> " + safe_new + "<br/>" if (new_tier and not old_tier) else ""}
          {"<b>Commission:</b> " + safe_comm + "%<br/>" if commission_pct else ""}
        </div>
      </div>

      <p>If you have any questions, simply reply to this email or reach us on <a href="{WHATSAPP_URL}">WhatsApp</a>.</p>

      <p style="margin-top:18px;color:#444;">Best regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=_branded(subject, html_body))


def send_partner_collaboration_closed_email(
    to_email: str,
    partner_name: str | None = None,
    reason: str | None = None,
) -> None:
    """
    Email inviata quando un admin disattiva un partner (chiusura collaborazione).
    """
    name = (partner_name or "Partner").strip()
    safe_name = escape(name)
    safe_reason = escape(reason.strip()) if reason else ""

    subject = "VoiceGuide — Collaboration Update"

    # TEXT (EN)
    lines = [
        f"Hello {name},",
        "",
        "We want to thank you for your collaboration as a VoiceGuide Partner.",
        "",
        "Your partner collaboration has been set to inactive by our admin team.",
    ]
    if reason and reason.strip():
        lines += ["", f"Reason: {reason.strip()}"]
    lines += [
        "",
        "If you believe this is a mistake or you need further details, simply reply to this email or reach us on WhatsApp:",
        WHATSAPP_URL,
        "",
        "Thank you again for the time we spent working together.",
        "",
        "Kind regards,",
        "VoiceGuide Team",
    ]
    text_body = "\n".join(lines)

    # HTML (EN)
    reason_html = ""
    if safe_reason:
        reason_html = f"""
        <div style="margin-top:10px;padding:12px;border-radius:10px;background:#fafafa;border:1px solid #eaeaea;">
          <div style="font-size:12px;color:#666;margin-bottom:6px;">Reason</div>
          <div style="font-size:14px;color:#111;">{safe_reason}</div>
        </div>
        """.strip()

    html_body = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
      <p>Hello <b>{safe_name}</b>,</p>

      <p>We want to thank you for your collaboration as a <b>VoiceGuide Partner</b>.</p>

      <p>Your partner collaboration has been set to <b>inactive</b> by our admin team.</p>

      {reason_html}

      <p style="margin-top:14px;">
        If you believe this is a mistake or you need further details, simply reply to this email or reach us on <a href="{WHATSAPP_URL}">WhatsApp</a>.
      </p>

      <p style="margin-top:14px;">Thank you again for the time we spent working together.</p>

      <p style="margin-top:18px;color:#444;">Kind regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=_branded(subject, html_body))


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


