# app/partner_emails.py
"""
Email alla ricezione di una candidatura partner (restyle 2026-10):
- conferma a chi si candida, in 5 lingue, stesso stile delle email nuove;
- avviso all'admin (PARTNER_NOTIFY_EMAIL, default stefano@voiceguideapp.com);
- approvazione, rifiuto, cambio di livello e chiusura, in 5 lingue (in fondo).
"""
import os
from html import escape

from app.email_service import _send_email
from app.email_layout import SITE_URL, WHATSAPP_URL, details, layout as _layout, norm_lang, p

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


# ---------------------------------------------------------------------------
# Email ai partner dopo la candidatura (prima solo in inglese, 2026-10-23):
# approvazione, rifiuto, cambio di livello, chiusura della collaborazione.
# La lingua e' quella del sito da cui si e' candidato (partners.language).
# ---------------------------------------------------------------------------
PARTNER_PORTAL_URL = "https://voiceguide-partner-production.up.railway.app"

PT = {
    "it": {
        "hello": "Ciao {name},",
        "tier": "Livello",
        "commission": "Commissione",
        "help": "Domande? Rispondi a questa email o scrivici su WhatsApp.",
        "signoff": "Il team VoiceGuide",
        "ok_subject": "VoiceGuide AirLink — La tua candidatura partner è approvata",
        "ok_title": "Candidatura approvata",
        "ok_intro": "la tua candidatura al programma partner di VoiceGuide AirLink è stata approvata.",
        "ok_code": "Il tuo codice partner",
        "ok_how": "Chi acquista con il tuo codice ha il 5% di sconto e tu ricevi la tua commissione su ogni acquisto.",
        "ok_link": "Puoi anche condividere il tuo link personale: chi arriva da qui trova lo sconto già inserito.",
        "ok_dash": "Nella dashboard partner vedi ordini e commissioni. Accedi con la tua email e il codice partner.",
        "ok_button": "Apri la dashboard partner",
        "no_subject": "VoiceGuide AirLink — La tua candidatura partner",
        "no_title": "Grazie per la tua candidatura",
        "no_body": "grazie per l'interesse verso il programma partner di VoiceGuide AirLink. Dopo averla valutata, per ora non possiamo approvare la tua candidatura.",
        "no_more": "Se vuoi saperne di più o ricandidarti in futuro, rispondi a questa email o scrivici su WhatsApp.",
        "tier_subject": "VoiceGuide AirLink — Il tuo livello partner è cambiato",
        "tier_title": "Il tuo livello partner è cambiato",
        "tier_body": "abbiamo aggiornato il tuo livello nel programma partner di VoiceGuide AirLink.",
        "end_subject": "VoiceGuide AirLink — La tua collaborazione partner",
        "end_title": "Aggiornamento sulla collaborazione",
        "end_body": "ti ringraziamo per la collaborazione come partner di VoiceGuide AirLink. La collaborazione è stata chiusa e il tuo codice partner non è più attivo.",
        "end_reason": "Motivo",
        "end_more": "Se pensi che sia un errore o vuoi più dettagli, rispondi a questa email o scrivici su WhatsApp.",
        "end_thanks": "Grazie ancora per il lavoro fatto insieme.",
    },
    "en": {
        "hello": "Hello {name},",
        "tier": "Tier",
        "commission": "Commission",
        "help": "Questions? Reply to this email or message us on WhatsApp.",
        "signoff": "The VoiceGuide team",
        "ok_subject": "VoiceGuide AirLink — Your partner application is approved",
        "ok_title": "Application approved",
        "ok_intro": "your application to the VoiceGuide AirLink partner program has been approved.",
        "ok_code": "Your partner code",
        "ok_how": "Customers who buy with your code get 5% off, and you earn your commission on every purchase.",
        "ok_link": "You can also share your personal link: anyone who arrives through it finds the discount already applied.",
        "ok_dash": "Your partner dashboard shows your orders and commissions. Log in with your email and partner code.",
        "ok_button": "Open the partner dashboard",
        "no_subject": "VoiceGuide AirLink — Your partner application",
        "no_title": "Thank you for applying",
        "no_body": "thank you for your interest in the VoiceGuide AirLink partner program. After reviewing your application, we're unable to approve it at this time.",
        "no_more": "If you'd like more information or want to apply again in the future, reply to this email or message us on WhatsApp.",
        "tier_subject": "VoiceGuide AirLink — Your partner tier has changed",
        "tier_title": "Your partner tier has changed",
        "tier_body": "we've updated your tier in the VoiceGuide AirLink partner program.",
        "end_subject": "VoiceGuide AirLink — Your partner collaboration",
        "end_title": "Collaboration update",
        "end_body": "thank you for your collaboration as a VoiceGuide AirLink partner. The collaboration has been closed and your partner code is no longer active.",
        "end_reason": "Reason",
        "end_more": "If you think this is a mistake or need more details, reply to this email or message us on WhatsApp.",
        "end_thanks": "Thank you again for the work we did together.",
    },
    "fr": {
        "hello": "Bonjour {name},",
        "tier": "Niveau",
        "commission": "Commission",
        "help": "Des questions ? Répondez à cet e-mail ou écrivez-nous sur WhatsApp.",
        "signoff": "L'équipe VoiceGuide",
        "ok_subject": "VoiceGuide AirLink — Votre candidature partenaire est acceptée",
        "ok_title": "Candidature acceptée",
        "ok_intro": "votre candidature au programme partenaire VoiceGuide AirLink a été acceptée.",
        "ok_code": "Votre code partenaire",
        "ok_how": "Les clients qui achètent avec votre code ont 5 % de réduction, et vous recevez votre commission sur chaque achat.",
        "ok_link": "Vous pouvez aussi partager votre lien personnel : ceux qui arrivent par ce lien trouvent la réduction déjà appliquée.",
        "ok_dash": "Votre espace partenaire affiche vos commandes et vos commissions. Connectez-vous avec votre e-mail et votre code partenaire.",
        "ok_button": "Ouvrir l'espace partenaire",
        "no_subject": "VoiceGuide AirLink — Votre candidature partenaire",
        "no_title": "Merci pour votre candidature",
        "no_body": "merci pour votre intérêt pour le programme partenaire VoiceGuide AirLink. Après l'avoir étudiée, nous ne pouvons pas accepter votre candidature pour le moment.",
        "no_more": "Pour en savoir plus ou pour postuler à nouveau plus tard, répondez à cet e-mail ou écrivez-nous sur WhatsApp.",
        "tier_subject": "VoiceGuide AirLink — Votre niveau partenaire a changé",
        "tier_title": "Votre niveau partenaire a changé",
        "tier_body": "nous avons mis à jour votre niveau dans le programme partenaire VoiceGuide AirLink.",
        "end_subject": "VoiceGuide AirLink — Votre collaboration partenaire",
        "end_title": "Point sur la collaboration",
        "end_body": "merci pour votre collaboration en tant que partenaire VoiceGuide AirLink. La collaboration a pris fin et votre code partenaire n'est plus actif.",
        "end_reason": "Motif",
        "end_more": "Si vous pensez qu'il s'agit d'une erreur ou souhaitez plus de détails, répondez à cet e-mail ou écrivez-nous sur WhatsApp.",
        "end_thanks": "Merci encore pour le travail accompli ensemble.",
    },
    "es": {
        "hello": "Hola, {name}:",
        "tier": "Nivel",
        "commission": "Comisión",
        "help": "¿Dudas? Responde a este email o escríbenos por WhatsApp.",
        "signoff": "El equipo de VoiceGuide",
        "ok_subject": "VoiceGuide AirLink — Tu solicitud de partner está aprobada",
        "ok_title": "Solicitud aprobada",
        "ok_intro": "tu solicitud al programa de partners de VoiceGuide AirLink ha sido aprobada.",
        "ok_code": "Tu código de partner",
        "ok_how": "Quien compra con tu código tiene un 5% de descuento y tú recibes tu comisión por cada compra.",
        "ok_link": "También puedes compartir tu enlace personal: quien llega desde él encuentra el descuento ya aplicado.",
        "ok_dash": "En el panel de partner ves tus pedidos y comisiones. Entra con tu email y tu código de partner.",
        "ok_button": "Abrir el panel de partner",
        "no_subject": "VoiceGuide AirLink — Tu solicitud de partner",
        "no_title": "Gracias por tu solicitud",
        "no_body": "gracias por tu interés en el programa de partners de VoiceGuide AirLink. Después de revisarla, por ahora no podemos aprobar tu solicitud.",
        "no_more": "Si quieres más información o volver a solicitarlo en el futuro, responde a este email o escríbenos por WhatsApp.",
        "tier_subject": "VoiceGuide AirLink — Tu nivel de partner ha cambiado",
        "tier_title": "Tu nivel de partner ha cambiado",
        "tier_body": "hemos actualizado tu nivel en el programa de partners de VoiceGuide AirLink.",
        "end_subject": "VoiceGuide AirLink — Tu colaboración como partner",
        "end_title": "Novedades sobre la colaboración",
        "end_body": "gracias por tu colaboración como partner de VoiceGuide AirLink. La colaboración ha finalizado y tu código de partner ya no está activo.",
        "end_reason": "Motivo",
        "end_more": "Si crees que es un error o quieres más detalles, responde a este email o escríbenos por WhatsApp.",
        "end_thanks": "Gracias de nuevo por el trabajo que hemos hecho juntos.",
    },
    "de": {
        "hello": "Hallo {name},",
        "tier": "Stufe",
        "commission": "Provision",
        "help": "Fragen? Antworten Sie auf diese E-Mail oder schreiben Sie uns auf WhatsApp.",
        "signoff": "Ihr VoiceGuide-Team",
        "ok_subject": "VoiceGuide AirLink — Ihre Partner-Bewerbung wurde angenommen",
        "ok_title": "Bewerbung angenommen",
        "ok_intro": "Ihre Bewerbung für das Partnerprogramm von VoiceGuide AirLink wurde angenommen.",
        "ok_code": "Ihr Partnercode",
        "ok_how": "Wer mit Ihrem Code kauft, erhält 5 % Rabatt, und Sie erhalten Ihre Provision auf jeden Kauf.",
        "ok_link": "Sie können auch Ihren persönlichen Link teilen: Wer darüber kommt, findet den Rabatt schon eingetragen.",
        "ok_dash": "Im Partner-Dashboard sehen Sie Ihre Bestellungen und Provisionen. Melden Sie sich mit Ihrer E-Mail und Ihrem Partnercode an.",
        "ok_button": "Partner-Dashboard öffnen",
        "no_subject": "VoiceGuide AirLink — Ihre Partner-Bewerbung",
        "no_title": "Danke für Ihre Bewerbung",
        "no_body": "vielen Dank für Ihr Interesse am Partnerprogramm von VoiceGuide AirLink. Nach Prüfung können wir Ihre Bewerbung derzeit leider nicht annehmen.",
        "no_more": "Wenn Sie mehr wissen oder sich später erneut bewerben möchten, antworten Sie auf diese E-Mail oder schreiben Sie uns auf WhatsApp.",
        "tier_subject": "VoiceGuide AirLink — Ihre Partnerstufe hat sich geändert",
        "tier_title": "Ihre Partnerstufe hat sich geändert",
        "tier_body": "wir haben Ihre Stufe im Partnerprogramm von VoiceGuide AirLink aktualisiert.",
        "end_subject": "VoiceGuide AirLink — Ihre Partnerschaft",
        "end_title": "Neuigkeiten zur Zusammenarbeit",
        "end_body": "vielen Dank für Ihre Zusammenarbeit als Partner von VoiceGuide AirLink. Die Zusammenarbeit wurde beendet, und Ihr Partnercode ist nicht mehr aktiv.",
        "end_reason": "Grund",
        "end_more": "Wenn Sie glauben, dass es sich um einen Fehler handelt, oder mehr erfahren möchten, antworten Sie auf diese E-Mail oder schreiben Sie uns auf WhatsApp.",
        "end_thanks": "Nochmals vielen Dank für die gemeinsame Arbeit.",
    },
}


def _pt(language: str | None) -> tuple[str, dict]:
    lang = norm_lang(language or "it")
    return lang, PT[lang]


def _greeting(t: dict, name: str | None, sentence: str) -> tuple[str, str]:
    """("Ciao Mario,", "Frase...") : saluto su una riga, poi la frase con la maiuscola."""
    return t["hello"].format(name=(name or "Partner").strip()), sentence[:1].upper() + sentence[1:]


def _rows(pairs: list[tuple[str, str]]) -> str:
    return details(pairs) if pairs else ""


def _send(to_email: str, subject: str, title: str, lang: str, paragraphs_html: str, text_lines: list[str]) -> None:
    _send_email(
        to_email=to_email,
        subject=subject,
        text_body="\n".join([title, ""] + text_lines),
        html_body=_layout(title, paragraphs_html, lang),
    )


def send_partner_approved_email(
    to_email: str,
    referral_code: str,
    partner_name: str | None = None,
    commission_pct: str | None = None,
    tier: str | None = None,
    language: str | None = None,
) -> None:
    lang, t = _pt(language)
    link = f"{SITE_URL}/{lang}?ref={referral_code}"
    pairs = [(t["tier"], str(tier))] if tier else []
    if commission_pct:
        pairs.append((t["commission"], f"{commission_pct}%"))
    hi, intro = _greeting(t, partner_name, t["ok_intro"])
    html = f"""
      {p(hi)}
      {p(intro)}
      <p style="margin:0 0 8px;font-size:15px;font-weight:bold;">{escape(t["ok_code"])}</p>
      <div style="text-align:center;margin:0 0 18px;">
        <span style="display:inline-block;background:#FFF1C7;border:2px dashed #FFC226;border-radius:14px;padding:12px 22px;font-size:24px;font-weight:bold;letter-spacing:2px;">{escape(referral_code)}</span>
      </div>
      {_rows(pairs)}
      {p(t["ok_how"])}
      {p(t["ok_link"])}
      <p style="margin:0 0 20px;font-size:14px;word-break:break-all;"><a href="{escape(link)}" style="color:#9A6B00;font-weight:bold;">{escape(link)}</a></p>
      {p(t["ok_dash"])}
      <p style="margin:0 0 22px;"><a href="{PARTNER_PORTAL_URL}" style="display:inline-block;background:#FFC226;color:#14161B;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 20px;border-radius:999px;">{escape(t["ok_button"])} →</a></p>
      {p(t["help"])}
      <p style="margin:0;font-size:14px;color:#14161B;">{escape(t["signoff"])}</p>
    """
    text = [hi, "", intro, "", f"{t['ok_code']}: {referral_code}"]
    text += [f"{k}: {v}" for k, v in pairs]
    text += ["", t["ok_how"], "", t["ok_link"], link, "", t["ok_dash"], PARTNER_PORTAL_URL, "", t["help"], WHATSAPP_URL, "", t["signoff"]]
    _send(to_email, t["ok_subject"], t["ok_title"], lang, html, text)


def send_partner_rejected_email(to_email: str, partner_name: str | None = None, language: str | None = None) -> None:
    lang, t = _pt(language)
    hi, body = _greeting(t, partner_name, t["no_body"])
    html = f"""
      {p(hi)}
      {p(body)}
      {p(t["no_more"])}
      <p style="margin:0;font-size:14px;color:#14161B;">{escape(t["signoff"])}</p>
    """
    _send(to_email, t["no_subject"], t["no_title"], lang, html, [hi, "", body, "", t["no_more"], WHATSAPP_URL, "", t["signoff"]])


def send_partner_tier_email(
    to_email: str,
    partner_name: str | None = None,
    old_tier: str | None = None,
    new_tier: str | None = None,
    commission_pct: str | None = None,
    language: str | None = None,
) -> None:
    lang, t = _pt(language)
    pairs = []
    if new_tier:
        pairs.append((t["tier"], f"{old_tier} → {new_tier}" if old_tier and old_tier != new_tier else str(new_tier)))
    if commission_pct:
        pairs.append((t["commission"], f"{commission_pct}%"))
    hi, body = _greeting(t, partner_name, t["tier_body"])
    html = f"""
      {p(hi)}
      {p(body)}
      {_rows(pairs)}
      {p(t["help"])}
      <p style="margin:0;font-size:14px;color:#14161B;">{escape(t["signoff"])}</p>
    """
    text = [hi, "", body, ""] + [f"{k}: {v}" for k, v in pairs] + ["", t["help"], WHATSAPP_URL, "", t["signoff"]]
    _send(to_email, t["tier_subject"], t["tier_title"], lang, html, text)


def send_partner_closed_email(
    to_email: str,
    partner_name: str | None = None,
    reason: str | None = None,
    language: str | None = None,
) -> None:
    lang, t = _pt(language)
    hi, body = _greeting(t, partner_name, t["end_body"])
    reason = (reason or "").strip()
    html = f"""
      {p(hi)}
      {p(body)}
      {_rows([(t["end_reason"], reason)]) if reason else ""}
      {p(t["end_more"])}
      {p(t["end_thanks"])}
      <p style="margin:0;font-size:14px;color:#14161B;">{escape(t["signoff"])}</p>
    """
    text = [hi, "", body, ""] + ([f"{t['end_reason']}: {reason}", ""] if reason else []) + [t["end_more"], WHATSAPP_URL, "", t["end_thanks"], "", t["signoff"]]
    _send(to_email, t["end_subject"], t["end_title"], lang, html, text)
