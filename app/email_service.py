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
    """
    Email inviata quando creiamo un ordine "reale" in DB ma pagamento ancora PENDING.
    Utile per attivare subito:
    - tracciamento ordini in Admin
    - invio email immediato
    anche prima di integrare Stripe/PayPal.
    """
    lang = (language or "en").strip().lower()
    friendly_product = _friendly_product_label(product, lang)
    has_discount = discount_amount and discount_amount > 0
    subtotal_amount = total_amount + discount_amount

    if lang == "it":
        subject = "VoiceGuide — Ordine ricevuto ✅"
        inv_line = "Fattura richiesta: SÌ" if invoice_requested else "Fattura richiesta: NO"
        if invoice_requested and intestatario:
            inv_line += f" ({intestatario})"

        amount_lines = (
            [
                f"Subtotale: €{subtotal_amount:.2f}",
                f"Sconto applicato: -€{discount_amount:.2f}",
                f"Totale da pagare: €{total_amount:.2f}",
            ]
            if has_discount
            else [f"Totale da pagare: €{total_amount:.2f}"]
        )

        text_body = "\n".join(
            [
                "Ciao,",
                "",
                "Abbiamo ricevuto il tuo ordine su VoiceGuide.",
                "",
                f"Ordine nr.: {order_id}",
                f"Prodotto: {friendly_product}",
                *amount_lines,
                inv_line,
                "",
                "Stato pagamento: IN ATTESA",
                "",
                "Ti invieremo un'email di conferma appena il pagamento sarà completato.",
                "",
                "Domande? Rispondi a questa email oppure scrivici su WhatsApp:",
                WHATSAPP_URL,
                "",
                "Un saluto,",
                "VoiceGuide Team",
            ]
        )

        amount_html = (
            f"""
              <b>Subtotale:</b> €{subtotal_amount:.2f}<br/>
              <b>Sconto applicato:</b> -€{discount_amount:.2f}<br/>
              <b>Totale da pagare:</b> €{total_amount:.2f}<br/>
            """
            if has_discount
            else f"<b>Totale da pagare:</b> €{total_amount:.2f}<br/>"
        )

        html_body = f"""
        <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
          <p>Ciao,</p>

          <p>Abbiamo ricevuto il tuo ordine su <b>VoiceGuide</b>.</p>

          <div style="padding:14px;border:1px solid #e5e5e5;border-radius:10px;margin:16px 0;">
            <div style="font-size:12px;color:#666;margin-bottom:6px;">Dettagli ordine</div>
            <div style="font-size:14px;">
              <b>Ordine nr.:</b> {order_id}<br/>
              <b>Prodotto:</b> {escape(friendly_product)}<br/>
              {amount_html}
              <b>{escape(inv_line)}</b><br/>
              <b>Stato pagamento:</b> IN ATTESA
            </div>
          </div>

          <p>Ti invieremo un'email di conferma appena il pagamento sarà completato.</p>

          <p>Domande? Rispondi a questa email oppure scrivici su <a href="{WHATSAPP_URL}">WhatsApp</a>.</p>

          <p style="margin-top:18px;color:#444;">Un saluto,<br/><b>VoiceGuide Team</b></p>
        </div>
        """.strip()

    else:
        subject = "VoiceGuide — Order received ✅"
        inv_line = "Invoice requested: YES" if invoice_requested else "Invoice requested: NO"
        if invoice_requested and intestatario:
            inv_line += f" ({intestatario})"

        amount_lines = (
            [
                f"Subtotal: €{subtotal_amount:.2f}",
                f"Discount applied: -€{discount_amount:.2f}",
                f"Total to pay: €{total_amount:.2f}",
            ]
            if has_discount
            else [f"Total to pay: €{total_amount:.2f}"]
        )

        text_body = "\n".join(
            [
                "Hello,",
                "",
                "We have received your order on VoiceGuide.",
                "",
                f"Order ID: {order_id}",
                f"Product: {friendly_product}",
                *amount_lines,
                inv_line,
                "",
                "Payment status: PENDING",
                "",
                "We will send you a confirmation email as soon as the payment is completed.",
                "",
                "Questions? Reply to this email or reach us on WhatsApp:",
                WHATSAPP_URL,
                "",
                "Best regards,",
                "VoiceGuide Team",
            ]
        )

        amount_html = (
            f"""
              <b>Subtotal:</b> €{subtotal_amount:.2f}<br/>
              <b>Discount applied:</b> -€{discount_amount:.2f}<br/>
              <b>Total to pay:</b> €{total_amount:.2f}<br/>
            """
            if has_discount
            else f"<b>Total to pay:</b> €{total_amount:.2f}<br/>"
        )

        html_body = f"""
        <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
          <p>Hello,</p>

          <p>We have received your order on <b>VoiceGuide</b>.</p>

          <div style="padding:14px;border:1px solid #e5e5e5;border-radius:10px;margin:16px 0;">
            <div style="font-size:12px;color:#666;margin-bottom:6px;">Order details</div>
            <div style="font-size:14px;">
              <b>Order ID:</b> {order_id}<br/>
              <b>Product:</b> {escape(friendly_product)}<br/>
              {amount_html}
              <b>{escape(inv_line)}</b><br/>
              <b>Payment status:</b> PENDING
            </div>
          </div>

          <p>We will send you a confirmation email as soon as the payment is completed.</p>

          <p>Questions? Reply to this email or reach us on <a href="{WHATSAPP_URL}">WhatsApp</a>.</p>

          <p style="margin-top:18px;color:#444;">Best regards,<br/><b>VoiceGuide Team</b></p>
        </div>
        """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


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
        "If you have any questions, simply reply to this email — our support team will be happy to assist you.",
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
      <p>If you have any questions, simply reply to this email — our support team will be happy to assist you.</p>

      <p style="margin-top:18px;color:#444;">Best regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


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
            "If you would like further information or wish to submit a new request in the future, feel free to reply to this email.",
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

      <p>If you would like further information or wish to submit a new request in the future, feel free to reply to this email.</p>

      <p style="margin-top:18px;color:#444;">Kind regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


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
        "If you have any questions, simply reply to this email.",
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

      <p>If you have any questions, simply reply to this email.</p>

      <p style="margin-top:18px;color:#444;">Best regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


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
        "This is a notification regarding your VoiceGuide Partner collaboration.",
        "",
        "Your collaboration has been set to inactive by our admin team.",
    ]
    if reason and reason.strip():
        lines += ["", f"Reason: {reason.strip()}"]
    lines += [
        "",
        "If you believe this is a mistake or you need further details, simply reply to this email.",
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

      <p>This is a notification regarding your <b>VoiceGuide Partner</b> collaboration.</p>

      <p>Your collaboration has been set to <b>inactive</b> by our admin team.</p>

      {reason_html}

      <p style="margin-top:14px;">
        If you believe this is a mistake or you need further details, simply reply to this email.
      </p>

      <p style="margin-top:18px;color:#444;">Kind regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


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
    lang = (language or "en").strip().lower()
    display_name = (name or "").strip()

    if lang == "it":
        subject = "VoiceGuide — Il tuo codice di licenza di prova 🎧"
        greeting = f"Ciao {display_name}," if display_name else "Ciao,"
        html_greeting = f"Ciao <b>{escape(display_name)}</b>," if display_name else "Ciao,"

        text_body = "\n".join(
            [
                greeting,
                "",
                "Grazie per aver scelto di provare VoiceGuide AirLink! Ecco il tuo codice di licenza di prova:",
                "",
                license_code,
                "",
                f"Ospiti massimi: {max_guests}",
                "",
                "Come iniziare:",
                "1. Scarica l'app VoiceGuide AirLink sul tuo telefono (link qui sotto).",
                "2. Apri l'app, scegli \"Guida\" e tocca \"Attiva Licenza\": inserisci il codice sopra.",
                "3. Tocca \"Avvia Nuovo Tour\": l'app genererà un PIN.",
                "4. Fai scaricare l'app anche ai tuoi ospiti (stesso link) e dai loro il PIN per farli entrare, scegliendo \"Ospite\".",
                "",
                "Consiglio: per una qualità audio migliore, ti suggeriamo un piccolo microfono per la guida e degli auricolari per gli ospiti.",
                "",
                f"Google Play: {PLAY_STORE_URL}",
                f"App Store: {APP_STORE_URL}",
                "",
                "Da sapere: questa licenza non è nominativa — puoi condividerla con altre guide del tuo team, se ti serve.",
                "",
                f"Vuoi l'esperienza completa? Usa il codice {PARTNER_DISCOUNT_CODE} per avere il 5% di sconto quando acquisti una licenza:",
                PURCHASE_PAGE_URL,
                "",
                "Domande? Rispondi a questa email oppure scrivici su WhatsApp:",
                WHATSAPP_URL,
                "",
                "Un saluto,",
                "VoiceGuide Team",
            ]
        )

        html_body = f"""
        <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
          <p>{html_greeting}</p>
          <p>Grazie per aver scelto di provare <b>VoiceGuide AirLink</b>! Ecco il tuo codice di licenza di prova:</p>

          <div style="padding:14px;border:1px solid #e5e5e5;border-radius:10px;margin:16px 0;">
            <div style="font-size:12px;color:#666;margin-bottom:6px;">Codice licenza di prova</div>
            <div style="font-size:22px;letter-spacing:1px;"><b>{escape(license_code)}</b></div>
          </div>

          <p style="margin:0 0 12px 0;"><b>Ospiti massimi:</b> {max_guests}</p>

          <p style="margin:0 0 6px 0;"><b>Come iniziare:</b></p>
          <ol style="margin:0 0 12px 0;padding-left:20px;">
            <li>Scarica l'app VoiceGuide AirLink sul tuo telefono (link qui sotto).</li>
            <li>Apri l'app, scegli "Guida" e tocca "Attiva Licenza": inserisci il codice sopra.</li>
            <li>Tocca "Avvia Nuovo Tour": l'app genererà un PIN.</li>
            <li>Fai scaricare l'app anche ai tuoi ospiti (stesso link) e dai loro il PIN per farli entrare, scegliendo "Ospite".</li>
          </ol>

          <p style="margin:0 0 16px 0;color:#444;">
            💡 Consiglio: per una qualità audio migliore, ti suggeriamo un piccolo microfono per la guida e degli auricolari per gli ospiti.
          </p>

          <p style="margin:0 0 16px 0;">
            📱 <a href="{PLAY_STORE_URL}">Google Play</a> &nbsp;|&nbsp;
            🍏 <a href="{APP_STORE_URL}">App Store</a>
          </p>

          <p style="margin:0 0 16px 0;color:#444;">
            Da sapere: questa licenza <b>non è nominativa</b> — puoi condividerla con altre guide del tuo team, se ti serve.
          </p>

          <div style="padding:14px;border:1px solid #FFC226;border-radius:10px;margin:16px 0;background:#FFFBEF;">
            <p style="margin:0 0 8px 0;">Vuoi l'esperienza completa? Usa il codice <b>{escape(PARTNER_DISCOUNT_CODE)}</b> per avere il <b>5% di sconto</b> quando acquisti una licenza.</p>
            <p style="margin:0;"><a href="{PURCHASE_PAGE_URL}"><b>Acquista una licenza →</b></a></p>
          </div>

          <p>Domande? Rispondi a questa email oppure scrivici su <a href="{WHATSAPP_URL}">WhatsApp</a>.</p>

          <p style="margin-top:18px;color:#444;">Un saluto,<br/><b>VoiceGuide Team</b></p>
        </div>
        """.strip()

    else:
        subject = "VoiceGuide — Your Trial License Code 🎧"
        greeting = f"Hello {display_name}," if display_name else "Hello,"
        html_greeting = f"Hello <b>{escape(display_name)}</b>," if display_name else "Hello,"

        text_body = "\n".join(
            [
                greeting,
                "",
                "Thanks for choosing to try VoiceGuide AirLink! Here is your trial license code:",
                "",
                license_code,
                "",
                f"Max guests: {max_guests}",
                "",
                "Getting started:",
                "1. Download the VoiceGuide AirLink app on your phone (link below).",
                "2. Open the app, choose \"Guide\" and tap \"Activate License\": enter the code above.",
                "3. Tap \"Start New Tour\": the app will generate a PIN.",
                "4. Have your guests download the app too (same link) and give them the PIN to join, choosing \"Guest\".",
                "",
                "Tip: for better audio quality, we recommend a small microphone for the guide and earbuds/headphones for the guests.",
                "",
                f"Google Play: {PLAY_STORE_URL}",
                f"App Store: {APP_STORE_URL}",
                "",
                "Good to know: this license is not tied to a specific person — you can share it with other guides on your team if needed.",
                "",
                f"Want the full experience? Use code {PARTNER_DISCOUNT_CODE} for 5% off when you purchase a license:",
                PURCHASE_PAGE_URL,
                "",
                "Questions? Reply to this email or reach us on WhatsApp:",
                WHATSAPP_URL,
                "",
                "Best regards,",
                "VoiceGuide Team",
            ]
        )

        html_body = f"""
        <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
          <p>{html_greeting}</p>
          <p>Thanks for choosing to try <b>VoiceGuide AirLink</b>! Here is your trial license code:</p>

          <div style="padding:14px;border:1px solid #e5e5e5;border-radius:10px;margin:16px 0;">
            <div style="font-size:12px;color:#666;margin-bottom:6px;">Trial License Code</div>
            <div style="font-size:22px;letter-spacing:1px;"><b>{escape(license_code)}</b></div>
          </div>

          <p style="margin:0 0 12px 0;"><b>Max guests:</b> {max_guests}</p>

          <p style="margin:0 0 6px 0;"><b>Getting started:</b></p>
          <ol style="margin:0 0 12px 0;padding-left:20px;">
            <li>Download the VoiceGuide AirLink app on your phone (link below).</li>
            <li>Open the app, choose "Guide" and tap "Activate License": enter the code above.</li>
            <li>Tap "Start New Tour": the app will generate a PIN.</li>
            <li>Have your guests download the app too (same link) and give them the PIN to join, choosing "Guest".</li>
          </ol>

          <p style="margin:0 0 16px 0;color:#444;">
            💡 Tip: for better audio quality, we recommend a small microphone for the guide and earbuds/headphones for the guests.
          </p>

          <p style="margin:0 0 16px 0;">
            📱 <a href="{PLAY_STORE_URL}">Google Play</a> &nbsp;|&nbsp;
            🍏 <a href="{APP_STORE_URL}">App Store</a>
          </p>

          <p style="margin:0 0 16px 0;color:#444;">
            Good to know: this license is <b>not tied to a specific person</b> — you can share it with other guides on your team if needed.
          </p>

          <div style="padding:14px;border:1px solid #FFC226;border-radius:10px;margin:16px 0;background:#FFFBEF;">
            <p style="margin:0 0 8px 0;">Want the full experience? Use code <b>{escape(PARTNER_DISCOUNT_CODE)}</b> for <b>5% off</b> when you purchase a license.</p>
            <p style="margin:0;"><a href="{PURCHASE_PAGE_URL}"><b>Buy a license →</b></a></p>
          </div>

          <p>Questions? Reply to this email or reach us on <a href="{WHATSAPP_URL}">WhatsApp</a>.</p>

          <p style="margin-top:18px;color:#444;">Best regards,<br/><b>VoiceGuide Team</b></p>
        </div>
        """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)


def send_payment_received_email(
    to_email: str,
    order_id: int,
    product: str | None = None,
    license_code: str | None = None,
    license_codes: list[str] | None = None,
) -> None:
    """
    Email inviata quando Stripe/PayPal conferma il pagamento.

    ✅ Supporta sia:
      - singolo codice: license_code="VG-...."   (retro-compatibilità)
      - lista codici:  license_codes=[...]       (pacchetti)
    """
    subject = "VoiceGuide — Payment confirmed ✅"

    # Normalizza: se arriva una lista usala; altrimenti fallback al singolo
    codes: list[str] = []
    if license_codes:
        codes = [c.strip() for c in license_codes if (c or "").strip()]
    elif license_code and license_code.strip():
        codes = [license_code.strip()]

    lines = [
        "Hello,",
        "",
        "Your payment has been confirmed.",
        "",
        f"Order ID: {order_id}",
    ]
    if product:
        lines.append(f"Product: {product}")

    if codes:
        lines += ["", "Your license code(s):"]
        lines += [f"- {c}" for c in codes]

    lines += [
        "",
        "If you have any questions, just reply to this email.",
        "",
        "Best regards,",
        "VoiceGuide Team",
    ]
    text_body = "\n".join(lines)

    # HTML: blocco copiabile + (opzionale) lista
    license_html = ""
    if codes:
        safe_codes_text = "\n".join(codes)
        safe_codes_pre = escape(safe_codes_text)

        lis = "\n".join([f"<li style='margin:4px 0;'><code>{escape(c)}</code></li>" for c in codes])

        license_html = f"""
        <div style="padding:14px;border:1px solid #e5e5e5;border-radius:10px;margin:16px 0;">
          <div style="font-size:12px;color:#666;margin-bottom:10px;">Your License Code(s)</div>

          <div style="margin-bottom:10px;">
            <div style="font-size:12px;color:#666;margin-bottom:6px;">Copy &amp; paste</div>
            <pre style="margin:0;padding:12px;border-radius:10px;background:#fafafa;border:1px solid #eee;white-space:pre-wrap;word-break:break-word;font-size:13px;line-height:1.5;">{safe_codes_pre}</pre>
          </div>

          <div style="font-size:12px;color:#666;margin:12px 0 6px 0;">List</div>
          <ul style="margin:0;padding-left:18px;">
            {lis}
          </ul>
        </div>
        """.strip()

    html_body = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111;">
      <p>Hello,</p>
      <p>Your payment has been <b>confirmed</b>.</p>

      <div style="padding:14px;border:1px solid #e5e5e5;border-radius:10px;margin:16px 0;">
        <div style="font-size:12px;color:#666;margin-bottom:6px;">Order details</div>
        <div style="font-size:14px;">
          <b>Order ID:</b> {order_id}<br/>
          {"<b>Product:</b> " + escape(product) + "<br/>" if product else ""}
          <b>Status:</b> PAID
        </div>
      </div>

      {license_html}

      <p>If you have any questions, just reply to this email.</p>
      <p style="margin-top:18px;color:#444;">Best regards,<br/><b>VoiceGuide Team</b></p>
    </div>
    """.strip()

    _send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)
