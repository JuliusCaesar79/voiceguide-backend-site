# app/email_layout.py
"""
Aspetto comune delle email automatiche (restyle 2026-10): logo, scheda bianca
con barra gialla su fondo crema, pulsanti degli store e piè di pagina.
Tutto con stili in linea, perché i programmi di posta ignorano i fogli di stile.
"""
from html import escape
from urllib.parse import quote

SITE_URL = "https://www.voiceguideapp.com"
LOGO_URL = f"{SITE_URL}/brand/voiceguide-airlink-logo.png"
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.voiceguideairlinkbare&pcampaignid=web_share"
APP_STORE_URL = "https://apps.apple.com/it/app/voiceguide-airlink/id6757807346"
WHATSAPP_URL = "https://wa.me/393755908650"
# Link diretti alla scheda recensioni degli store
APP_STORE_REVIEW_URL = "https://apps.apple.com/app/id6757807346?action=write-review"
PLAY_STORE_REVIEW_URL = "https://play.google.com/store/apps/details?id=com.voiceguideairlinkbare&showAllReviews=true"

LANGS = ("it", "en", "fr", "es", "de")

# Nomi dei pulsanti presi dall'app (VoiceGuideAirlinkBare/app/i18n/locales).
STEPS = {
    "it": [
        "Scarica l'app VoiceGuide AirLink (link qui sotto).",
        "Apri l'app, scegli \"Guida\", tocca \"Attiva Licenza\" e inserisci un codice.",
        "Tocca \"Avvia Nuovo Tour\": l'app crea un PIN da dare al gruppo.",
        "Gli ospiti scaricano l'app, scelgono \"Ospite\" e inseriscono il PIN.",
    ],
    "en": [
        "Download the VoiceGuide AirLink app (links below).",
        "Open the app, choose \"Guide\", tap \"Activate License\" and enter a code.",
        "Tap \"Start New Tour\": the app creates a PIN for your group.",
        "Guests download the app, choose \"Guest\" and enter the PIN.",
    ],
    "fr": [
        "Téléchargez l'application VoiceGuide AirLink (liens ci-dessous).",
        "Ouvrez l'application, choisissez « Guide », touchez « Activer la Licence » et saisissez un code.",
        "Touchez « Démarrer une Nouvelle Visite » : l'application crée un PIN pour le groupe.",
        "Les participants téléchargent l'application, choisissent « Invité » et saisissent le PIN.",
    ],
    "es": [
        "Descarga la app VoiceGuide AirLink (enlaces abajo).",
        "Abre la app, elige \"Guía\", toca \"Activar Licencia\" e introduce un código.",
        "Toca \"Iniciar Nuevo Tour\": la app crea un PIN para el grupo.",
        "Los participantes descargan la app, eligen \"Invitado\" e introducen el PIN.",
    ],
    "de": [
        "Laden Sie die App VoiceGuide AirLink herunter (Links unten).",
        "Öffnen Sie die App, wählen Sie „Guide“, tippen Sie auf „Lizenz Aktivieren“ und geben Sie einen Code ein.",
        "Tippen Sie auf „Neue Tour Starten“: Die App erstellt eine PIN für die Gruppe.",
        "Die Gäste laden die App herunter, wählen „Gast“ und geben die PIN ein.",
    ],
}

COMMON = {
    "it": {"how": "Come si usa", "help": "Domande? Rispondi a questa email o scrivici su WhatsApp.", "signoff": "Il team VoiceGuide", "pricing": "Vedi i prezzi"},
    "en": {"how": "How to use it", "help": "Questions? Reply to this email or message us on WhatsApp.", "signoff": "The VoiceGuide team", "pricing": "See pricing"},
    "fr": {"how": "Comment l'utiliser", "help": "Des questions ? Répondez à cet e-mail ou écrivez-nous sur WhatsApp.", "signoff": "L'équipe VoiceGuide", "pricing": "Voir les tarifs"},
    "es": {"how": "Cómo se usa", "help": "¿Dudas? Responde a este email o escríbenos por WhatsApp.", "signoff": "El equipo de VoiceGuide", "pricing": "Ver precios"},
    "de": {"how": "So funktioniert es", "help": "Fragen? Antworten Sie auf diese E-Mail oder schreiben Sie uns auf WhatsApp.", "signoff": "Ihr VoiceGuide-Team", "pricing": "Preise ansehen"},
}


def norm_lang(language: str | None) -> str:
    lang = (language or "en").strip().lower()[:2]
    return lang if lang in LANGS else "en"


def layout(title: str, inner_html: str, lang: str) -> str:
    """Contenitore comune: logo, scheda bianca con barra gialla, store e piè di pagina."""
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


def p(text: str, muted: bool = False) -> str:
    color = "#5A5F6B" if muted else "#4A4F5A"
    size = "13px" if muted else "15px"
    return f'<p style="margin:0 0 16px;font-size:{size};line-height:1.6;color:{color};">{escape(text)}</p>'


def details(rows: list[tuple[str, str]]) -> str:
    """Riquadro crema con righe etichetta/valore (dettagli ordine)."""
    trs = "".join(
        f'<tr><td style="padding:8px 14px;font-size:13px;color:#5A5F6B;">{escape(k)}</td>'
        f'<td style="padding:8px 14px;font-size:15px;font-weight:bold;text-align:right;">{escape(v)}</td></tr>'
        for k, v in rows
    )
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="border-collapse:collapse;background:#FBF8F1;border-radius:14px;margin:0 0 20px;">'
        f"{trs}</table>"
    )


def codes_box(codes: list[tuple[str, str]]) -> str:
    """Codici licenza in evidenza: [(codice, nota a destra)]."""
    rows = "".join(
        f'<tr><td style="padding:12px 14px;border-bottom:1px solid #F1EBDD;font-size:18px;font-weight:bold;letter-spacing:1px;">{escape(c)}</td>'
        f'<td style="padding:12px 14px;border-bottom:1px solid #F1EBDD;font-size:14px;color:#4A4F5A;text-align:right;white-space:nowrap;">{escape(n)}</td></tr>'
        for c, n in codes
    )
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="border-collapse:collapse;background:#FFF8E6;border:2px solid #F2C94C;border-radius:14px;margin:0 0 20px;">'
        f"{rows}</table>"
    )


def steps_block(lang: str) -> str:
    items = "".join(f'<li style="margin:0 0 6px;">{escape(s)}</li>' for s in STEPS[lang])
    return (
        f'<p style="margin:0 0 8px;font-size:15px;font-weight:bold;">{escape(COMMON[lang]["how"])}</p>'
        f'<ol style="margin:0 0 18px;padding-left:20px;font-size:14px;line-height:1.55;color:#2A2E36;">{items}</ol>'
    )


# Pagina /join del sito: la guida la manda al gruppo il giorno prima, ogni
# ospite la vede nella lingua del proprio telefono.
JOIN_URL = "https://voiceguideapp.com/join"

GUESTS = {
    "it": {"title": "Prepara i tuoi ospiti", "text": "Il giorno prima manda al gruppo questo link: spiega, nella lingua di ognuno, come scaricare l'app gratuita e di portare gli auricolari. Così il tour parte in orario.", "whatsapp": "Invia su WhatsApp",
           "message": "Per la visita guidata useremo VoiceGuide AirLink: sentirai la guida nei tuoi auricolari. Prima del tour scarica l'app gratuita e porta gli auricolari:"},
    "en": {"title": "Get your guests ready", "text": "The day before, send your group this link: it explains, in each guest's language, how to download the free app and to bring earphones. That way the tour starts on time.", "whatsapp": "Send on WhatsApp",
           "message": "On our guided tour we'll use VoiceGuide AirLink: you'll hear the guide in your earphones. Before the tour, download the free app and bring your earphones:"},
    "fr": {"title": "Préparez vos participants", "text": "La veille, envoyez ce lien au groupe : il explique, dans la langue de chacun, comment télécharger l'application gratuite et d'apporter des écouteurs. Ainsi, la visite commence à l'heure.", "whatsapp": "Envoyer sur WhatsApp",
           "message": "Pour la visite guidée, nous utiliserons VoiceGuide AirLink : vous entendrez le guide dans vos écouteurs. Avant la visite, téléchargez l'application gratuite et apportez vos écouteurs :"},
    "es": {"title": "Prepara a tus participantes", "text": "El día antes, envía este enlace al grupo: explica, en el idioma de cada uno, cómo descargar la app gratuita y que lleven auriculares. Así el tour empieza a tiempo.", "whatsapp": "Enviar por WhatsApp",
           "message": "En la visita guiada usaremos VoiceGuide AirLink: oirás al guía en tus auriculares. Antes del tour, descarga la app gratuita y lleva tus auriculares:"},
    "de": {"title": "Bereiten Sie Ihre Gäste vor", "text": "Senden Sie der Gruppe am Vortag diesen Link: Er erklärt in der Sprache jedes Gastes, wie man die kostenlose App lädt und dass Kopfhörer mitzubringen sind. So startet die Tour pünktlich.", "whatsapp": "Per WhatsApp senden",
           "message": "Bei unserer Führung nutzen wir VoiceGuide AirLink: Sie hören den Guide in Ihren Kopfhörern. Laden Sie vor der Tour die kostenlose App herunter und bringen Sie Kopfhörer mit:"},
}


def guests_block(lang: str) -> str:
    g = GUESTS[lang]
    wa = "https://wa.me/?text=" + quote(f'{g["message"]} {JOIN_URL}')
    return (
        '<div style="background:#FFF1C7;border-radius:14px;padding:16px 18px;margin:0 0 20px;">'
        f'<p style="margin:0 0 6px;font-size:15px;font-weight:bold;">{escape(g["title"])}</p>'
        f'<p style="margin:0 0 10px;font-size:14px;line-height:1.55;color:#4A4F5A;">{escape(g["text"])}</p>'
        f'<p style="margin:0 0 12px;font-size:15px;font-weight:bold;"><a href="{JOIN_URL}" style="color:#9A6B00;">voiceguideapp.com/join</a></p>'
        f'<a href="{escape(wa)}" style="display:inline-block;background:#14161B;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:14px;padding:11px 18px;border-radius:999px;">{escape(g["whatsapp"])}</a>'
        "</div>"
    )


def guests_text(lang: str) -> list[str]:
    g = GUESTS[lang]
    return ["", g["title"], g["text"], JOIN_URL]


def store_buttons() -> str:
    btn = "display:inline-block;background:#14161B;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 18px;border-radius:999px;margin:0 6px 6px 0;"
    return f'<p style="margin:0 0 20px;"><a href="{APP_STORE_URL}" style="{btn}">App Store</a><a href="{PLAY_STORE_URL}" style="{btn}">Google Play</a></p>'


def button(label: str, url: str) -> str:
    return (
        f'<p style="margin:0 0 20px;"><a href="{url}" style="display:inline-block;background:#FFC226;color:#14161B;'
        f'text-decoration:none;font-weight:bold;font-size:15px;padding:13px 22px;border-radius:999px;">{escape(label)}</a></p>'
    )


def signoff(lang: str) -> str:
    c = COMMON[lang]
    return (
        f'<p style="margin:0 0 6px;font-size:14px;line-height:1.55;color:#4A4F5A;">{escape(c["help"])}</p>'
        f'<p style="margin:12px 0 0;font-size:14px;color:#14161B;">{escape(c["signoff"])}</p>'
    )


def steps_text(lang: str) -> list[str]:
    return [COMMON[lang]["how"]] + [f"{i}. {s}" for i, s in enumerate(STEPS[lang], 1)]


def footer_text(lang: str) -> list[str]:
    c = COMMON[lang]
    return ["", f"App Store: {APP_STORE_URL}", f"Google Play: {PLAY_STORE_URL}", "", c["help"], WHATSAPP_URL, "", c["signoff"]]
