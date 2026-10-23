# app/partner_emails.py
"""
Email alla ricezione di una candidatura partner (restyle 2026-10):
- conferma a chi si candida, in 5 lingue, stesso stile delle email nuove;
- avviso all'admin (PARTNER_NOTIFY_EMAIL, default stefano@voiceguideapp.com).
"""
import os
from html import escape

from app.email_service import _send_email
from app.email_layout import layout as _layout

TEXTS = {
    "it": ("Abbiamo ricevuto la tua candidatura", "Grazie {name}! Abbiamo ricevuto la tua candidatura al programma partner di VoiceGuide AirLink. La valutiamo e ti rispondiamo in ogni caso via email. Se viene approvata, riceverai il tuo codice partner personale.", "Il team VoiceGuide"),
    "en": ("We've received your application", "Thank you {name}! We've received your application to the VoiceGuide AirLink partner program. We'll review it and reply by email either way. If it's approved, you'll receive your personal partner code.", "The VoiceGuide team"),
    "fr": ("Nous avons bien reçu votre candidature", "Merci {name} ! Nous avons bien reçu votre candidature au programme partenaire VoiceGuide AirLink. Nous l'étudions et vous répondons par e-mail dans tous les cas. Si elle est acceptée, vous recevrez votre code partenaire personnel.", "L'équipe VoiceGuide"),
    "es": ("Hemos recibido tu solicitud", "¡Gracias {name}! Hemos recibido tu solicitud al programa de partners de VoiceGuide AirLink. La revisamos y te respondemos por email en cualquier caso. Si se aprueba, recibirás tu código de partner personal.", "El equipo de VoiceGuide"),
    "de": ("Wir haben Ihre Bewerbung erhalten", "Vielen Dank, {name}! Wir haben Ihre Bewerbung für das Partnerprogramm von VoiceGuide AirLink erhalten. Wir prüfen sie und antworten Ihnen in jedem Fall per E-Mail. Wird sie angenommen, erhalten Sie Ihren persönlichen Partnercode.", "Ihr VoiceGuide-Team"),
}


def send_partner_request_received_email(to_email: str, name: str, language: str = "it") -> None:
    lang = (language or "it").strip().lower()
    if lang not in TEXTS:
        lang = "en"
    title, body, signoff = TEXTS[lang]
    text = body.format(name=name)
    inner = f"""
      <p style="margin:0 0 18px;font-size:15px;line-height:1.6;color:#4A4F5A;">{escape(text)}</p>
      <p style="margin:0;font-size:14px;color:#14161B;">{escape(signoff)}</p>
    """
    _send_email(
        to_email=to_email,
        subject=f"VoiceGuide AirLink — {title}",
        text_body=f"{title}\n\n{text}\n\n{signoff}",
        html_body=_layout(title, inner, lang),
    )


def send_partner_request_admin_notice(name: str, email: str, organization: str | None, message: str | None) -> None:
    to = os.getenv("PARTNER_NOTIFY_EMAIL") or "stefano@voiceguideapp.com"
    lines = [
        "Nuova candidatura partner dal sito.",
        "",
        f"Nome: {name}",
        f"Email: {email}",
        f"Attività: {organization or '-'}",
        f"Messaggio: {message or '-'}",
        "",
        "La trovi nella dashboard admin, tra le richieste partner.",
    ]
    rows = "".join(
        f'<tr><td style="padding:6px 10px;color:#5A5F6B;font-size:13px;">{escape(k)}</td><td style="padding:6px 10px;font-size:14px;">{escape(v)}</td></tr>'
        for k, v in [("Nome", name), ("Email", email), ("Attività", organization or "-"), ("Messaggio", message or "-")]
    )
    inner = f"""
      <table role="presentation" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 16px;">{rows}</table>
      <p style="margin:0;font-size:14px;color:#4A4F5A;">La trovi nella dashboard admin, tra le richieste partner.</p>
    """
    _send_email(
        to_email=to,
        subject=f"Nuova candidatura partner: {name}",
        text_body="\n".join(lines),
        html_body=_layout("Nuova candidatura partner", inner, "it"),
    )
