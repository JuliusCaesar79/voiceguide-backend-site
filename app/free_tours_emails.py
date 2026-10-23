# app/free_tours_emails.py
"""
Email della registrazione gratuita (3 tour), in 5 lingue, con logo:
- send_free_tours_code_email: codice di conferma di 6 cifre;
- send_free_tours_licenses_email: i 3 codici licenza (5, 25, 35 ospiti).
Stile del sito rinnovato (fondo crema, giallo VoiceGuide).
"""
from html import escape

from app.email_service import APP_STORE_URL, PLAY_STORE_URL, WHATSAPP_URL, _send_email

SITE_URL = "https://www.voiceguideapp.com"
LOGO_URL = f"{SITE_URL}/brand/voiceguide-airlink-logo.png"

TEXTS = {
    "it": {
        "code_subject": "Il tuo codice VoiceGuide: {code}",
        "code_title": "Conferma la tua email",
        "code_intro": "Inserisci questo codice sul sito per ricevere i tuoi 3 tour gratuiti:",
        "code_expiry": "Il codice vale 15 minuti. Se non l'hai richiesto tu, ignora questa email.",
        "lic_subject": "I tuoi 3 tour gratuiti VoiceGuide AirLink 🎧",
        "lic_title": "Ecco i tuoi 3 tour gratuiti",
        "lic_intro": "Grazie per esserti registrato! Questi sono i tuoi codici licenza. Non scadono: usali quando vuoi.",
        "guests": "Fino a {n} ospiti",
        "how_title": "Come si usa",
        "steps": [
            "Scarica l'app VoiceGuide AirLink (link qui sotto).",
            "Apri l'app, scegli \"Guida\" e inserisci uno dei codici.",
            "Tocca \"Avvia Nuovo Tour\": l'app crea un PIN da dare al gruppo.",
            "Gli ospiti scaricano l'app, scelgono \"Ospite\" e inseriscono il PIN.",
        ],
        "notes": "Ogni licenza vale per un tour fino a 4 ore, che partono quando inserisci il codice nell'app. Le licenze non sono nominative: puoi passarle a un collega.",
        "buy": "Vedi i prezzi",
        "help": "Domande? Rispondi a questa email o scrivici su WhatsApp.",
        "signoff": "Il team VoiceGuide",
    },
    "en": {
        "code_subject": "Your VoiceGuide code: {code}",
        "code_title": "Confirm your email",
        "code_intro": "Enter this code on the website to get your 3 free tours:",
        "code_expiry": "The code is valid for 15 minutes. If you didn't request it, just ignore this email.",
        "lic_subject": "Your 3 free VoiceGuide AirLink tours 🎧",
        "lic_title": "Here are your 3 free tours",
        "lic_intro": "Thanks for signing up! These are your license codes. They never expire: use them whenever you like.",
        "guests": "Up to {n} guests",
        "how_title": "How to use them",
        "steps": [
            "Download the VoiceGuide AirLink app (links below).",
            "Open the app, choose \"Guide\" and enter one of the codes.",
            "Tap \"Start New Tour\": the app creates a PIN for your group.",
            "Guests download the app, choose \"Guest\" and enter the PIN.",
        ],
        "notes": "Each license covers one tour of up to 4 hours, starting when you enter the code in the app. Licenses aren't tied to a person: you can pass them to a colleague.",
        "buy": "See pricing",
        "help": "Questions? Reply to this email or message us on WhatsApp.",
        "signoff": "The VoiceGuide team",
    },
    "fr": {
        "code_subject": "Votre code VoiceGuide : {code}",
        "code_title": "Confirmez votre e-mail",
        "code_intro": "Saisissez ce code sur le site pour recevoir vos 3 visites offertes :",
        "code_expiry": "Le code est valable 15 minutes. Si vous ne l'avez pas demandé, ignorez cet e-mail.",
        "lic_subject": "Vos 3 visites offertes VoiceGuide AirLink 🎧",
        "lic_title": "Voici vos 3 visites offertes",
        "lic_intro": "Merci pour votre inscription ! Voici vos codes de licence. Ils n'expirent pas : utilisez-les quand vous voulez.",
        "guests": "Jusqu'à {n} participants",
        "how_title": "Comment les utiliser",
        "steps": [
            "Téléchargez l'application VoiceGuide AirLink (liens ci-dessous).",
            "Ouvrez l'application, choisissez « Guide » et saisissez l'un des codes.",
            "Touchez « Démarrer une Nouvelle Visite » : l'application crée un PIN pour le groupe.",
            "Les participants téléchargent l'application, choisissent « Invité » et saisissent le PIN.",
        ],
        "notes": "Chaque licence vaut pour une visite jusqu'à 4 heures, qui commencent quand vous saisissez le code dans l'application. Les licences ne sont pas nominatives : vous pouvez les transmettre à un collègue.",
        "buy": "Voir les tarifs",
        "help": "Des questions ? Répondez à cet e-mail ou écrivez-nous sur WhatsApp.",
        "signoff": "L'équipe VoiceGuide",
    },
    "es": {
        "code_subject": "Tu código VoiceGuide: {code}",
        "code_title": "Confirma tu email",
        "code_intro": "Introduce este código en la web para recibir tus 3 tours gratuitos:",
        "code_expiry": "El código es válido 15 minutos. Si no lo has pedido tú, ignora este email.",
        "lic_subject": "Tus 3 tours gratuitos de VoiceGuide AirLink 🎧",
        "lic_title": "Aquí tienes tus 3 tours gratuitos",
        "lic_intro": "¡Gracias por registrarte! Estos son tus códigos de licencia. No caducan: úsalos cuando quieras.",
        "guests": "Hasta {n} participantes",
        "how_title": "Cómo usarlos",
        "steps": [
            "Descarga la app VoiceGuide AirLink (enlaces abajo).",
            "Abre la app, elige \"Guía\" e introduce uno de los códigos.",
            "Toca \"Iniciar Nuevo Tour\": la app crea un PIN para el grupo.",
            "Los participantes descargan la app, eligen \"Invitado\" e introducen el PIN.",
        ],
        "notes": "Cada licencia vale para un tour de hasta 4 horas, que empiezan cuando introduces el código en la app. Las licencias no son nominativas: puedes pasárselas a un compañero.",
        "buy": "Ver precios",
        "help": "¿Dudas? Responde a este email o escríbenos por WhatsApp.",
        "signoff": "El equipo de VoiceGuide",
    },
    "de": {
        "code_subject": "Ihr VoiceGuide-Code: {code}",
        "code_title": "Bestätigen Sie Ihre E-Mail",
        "code_intro": "Geben Sie diesen Code auf der Website ein, um Ihre 3 Gratis-Touren zu erhalten:",
        "code_expiry": "Der Code ist 15 Minuten gültig. Wenn Sie ihn nicht angefordert haben, ignorieren Sie diese E-Mail.",
        "lic_subject": "Ihre 3 Gratis-Touren mit VoiceGuide AirLink 🎧",
        "lic_title": "Hier sind Ihre 3 Gratis-Touren",
        "lic_intro": "Danke für Ihre Registrierung! Das sind Ihre Lizenzcodes. Sie verfallen nicht: Nutzen Sie sie, wann Sie wollen.",
        "guests": "Bis zu {n} Gäste",
        "how_title": "So nutzen Sie sie",
        "steps": [
            "Laden Sie die App VoiceGuide AirLink herunter (Links unten).",
            "Öffnen Sie die App, wählen Sie „Guide“ und geben Sie einen der Codes ein.",
            "Tippen Sie auf „Neue Tour Starten“: Die App erstellt eine PIN für die Gruppe.",
            "Die Gäste laden die App herunter, wählen „Gast“ und geben die PIN ein.",
        ],
        "notes": "Jede Lizenz gilt für eine Tour bis zu 4 Stunden, die ab der Eingabe des Codes in der App laufen. Die Lizenzen sind nicht personengebunden: Sie können sie an Kollegen weitergeben.",
        "buy": "Preise ansehen",
        "help": "Fragen? Antworten Sie auf diese E-Mail oder schreiben Sie uns auf WhatsApp.",
        "signoff": "Ihr VoiceGuide-Team",
    },
}


def _t(language: str) -> tuple[str, dict]:
    lang = (language or "it").strip().lower()
    if lang not in TEXTS:
        lang = "en"
    return lang, TEXTS[lang]


def _layout(title: str, inner_html: str, lang: str) -> str:
    """Contenitore comune: logo, scheda bianca su fondo crema, link store."""
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#FBF8F1;">
<div style="background:#FBF8F1;padding:28px 12px;font-family:Arial,Helvetica,sans-serif;color:#14161B;">
  <div style="max-width:560px;margin:0 auto;">
    <div style="text-align:center;margin-bottom:18px;">
      <a href="{SITE_URL}/{lang}"><img src="{LOGO_URL}" alt="VoiceGuide AirLink" width="130" style="width:130px;height:auto;border:0;"></a>
    </div>
    <div style="background:#FFFFFF;border-radius:22px;overflow:hidden;border:1px solid #EEE7D6;box-shadow:0 10px 30px rgba(20,22,27,0.06);">
      <div style="height:8px;background:#FFC226;line-height:8px;font-size:0;">&nbsp;</div>
      <div style="padding:30px 28px;">
        <h1 style="margin:0 0 14px;font-size:24px;line-height:1.2;letter-spacing:-0.5px;">{escape(title)}</h1>
        {inner_html}
      </div>
    </div>
    <div style="text-align:center;margin-top:20px;font-size:13px;color:#5A5F6B;line-height:1.8;">
      <a href="{APP_STORE_URL}" style="color:#14161B;margin:0 8px;">App Store</a>
      <a href="{PLAY_STORE_URL}" style="color:#14161B;margin:0 8px;">Google Play</a>
      <a href="{WHATSAPP_URL}" style="color:#14161B;margin:0 8px;">WhatsApp</a><br>
      <a href="{SITE_URL}/{lang}" style="color:#5A5F6B;text-decoration:none;">VoiceGuide AirLink · voiceguideapp.com</a>
    </div>
  </div>
</div>
</body></html>"""


def send_free_tours_code_email(to_email: str, code: str, language: str = "it") -> None:
    lang, t = _t(language)
    inner = f"""
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#4A4F5A;">{escape(t["code_intro"])}</p>
      <div style="text-align:center;margin:0 0 18px;">
        <span style="display:inline-block;background:#FFF1C7;border:2px dashed #FFC226;border-radius:14px;padding:14px 24px;font-size:32px;font-weight:bold;letter-spacing:8px;">{escape(code)}</span>
      </div>
      <p style="margin:0;font-size:13px;line-height:1.5;color:#5A5F6B;">{escape(t["code_expiry"])}</p>
    """
    text = "\n".join([t["code_title"], "", t["code_intro"], "", code, "", t["code_expiry"]])
    _send_email(
        to_email=to_email,
        subject=t["code_subject"].format(code=code),
        text_body=text,
        html_body=_layout(t["code_title"], inner, lang),
    )


def send_free_tours_licenses_email(
    to_email: str,
    licenses: list[tuple[str, int]],
    language: str = "it",
) -> None:
    """licenses: [(codice, ospiti_max), ...]"""
    lang, t = _t(language)
    pricing_url = f"{SITE_URL}/{lang}#prezzi"

    rows = "".join(
        f"""<tr>
          <td style="padding:10px 12px;border-bottom:1px solid #F1EBDD;font-size:18px;font-weight:bold;letter-spacing:1px;">{escape(code)}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #F1EBDD;font-size:14px;color:#4A4F5A;text-align:right;white-space:nowrap;">{escape(t["guests"].format(n=n))}</td>
        </tr>"""
        for code, n in licenses
    )
    steps = "".join(f"<li style=\"margin:0 0 6px;\">{escape(s)}</li>" for s in t["steps"])

    inner = f"""
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#4A4F5A;">{escape(t["lic_intro"])}</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#FFF8E6;border:2px solid #F2C94C;border-radius:14px;margin:0 0 20px;">
        {rows}
      </table>
      <p style="margin:0 0 8px;font-size:15px;font-weight:bold;">{escape(t["how_title"])}</p>
      <ol style="margin:0 0 16px;padding-left:20px;font-size:14px;line-height:1.55;color:#2A2E36;">{steps}</ol>
      <p style="margin:0 0 20px;font-size:13px;line-height:1.55;color:#5A5F6B;">{escape(t["notes"])}</p>
      <p style="margin:0 0 20px;">
        <a href="{APP_STORE_URL}" style="display:inline-block;background:#14161B;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 18px;border-radius:999px;margin:0 6px 6px 0;">App Store</a>
        <a href="{PLAY_STORE_URL}" style="display:inline-block;background:#14161B;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 18px;border-radius:999px;margin:0 6px 6px 0;">Google Play</a>
      </p>
      <p style="margin:0 0 6px;font-size:14px;line-height:1.55;color:#4A4F5A;">{escape(t["help"])}</p>
      <p style="margin:0 0 20px;font-size:14px;"><a href="{pricing_url}" style="color:#9A6B00;font-weight:bold;">{escape(t["buy"])} →</a></p>
      <p style="margin:0;font-size:14px;color:#14161B;">{escape(t["signoff"])}</p>
    """
    text_lines = [t["lic_title"], "", t["lic_intro"], ""]
    text_lines += [f"{code} — {t['guests'].format(n=n)}" for code, n in licenses]
    text_lines += ["", t["how_title"]]
    text_lines += [f"{i}. {s}" for i, s in enumerate(t["steps"], 1)]
    text_lines += ["", t["notes"], "", f"App Store: {APP_STORE_URL}", f"Google Play: {PLAY_STORE_URL}", "", t["help"], WHATSAPP_URL, "", t["signoff"]]

    _send_email(
        to_email=to_email,
        subject=t["lic_subject"],
        text_body="\n".join(text_lines),
        html_body=_layout(t["lic_title"], inner, lang),
    )
