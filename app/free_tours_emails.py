# app/free_tours_emails.py
"""
Email della registrazione gratuita (3 tour), in 5 lingue, con logo:
- send_free_tours_code_email: codice di conferma di 6 cifre;
- send_free_tours_licenses_email: i 3 codici licenza (5, 25, 35 ospiti).
Stile del sito rinnovato (fondo crema, giallo VoiceGuide).
"""
from html import escape

from app.email_layout import APP_STORE_URL, PLAY_STORE_URL, STEPS, WHATSAPP_URL, layout
from app.email_service import _send_email

SITE_URL = "https://www.voiceguideapp.com"

TEXTS = {
    "it": {
        "code_subject": "Il tuo codice VoiceGuide: {code}",
        "code_title": "Conferma la tua email",
        "code_intro": "Inserisci questo codice sul sito per ricevere i tuoi 3 tour gratuiti:",
        "code_expiry": "Il codice vale 15 minuti. Se non l'hai richiesto tu, ignora questa email.",
        "lic_subject": "I tuoi codici licenza VoiceGuide AirLink",
        "lic_title": "Ecco i tuoi 3 tour gratuiti",
        "lic_intro": "Grazie per esserti registrato! Questi sono i tuoi codici licenza. Non scadono: usali quando vuoi.",
        "guests": "Fino a {n} ospiti",
        "how_title": "Come si usa",
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
        "lic_subject": "Your VoiceGuide AirLink license codes",
        "lic_title": "Here are your 3 free tours",
        "lic_intro": "Thanks for signing up! These are your license codes. They never expire: use them whenever you like.",
        "guests": "Up to {n} guests",
        "how_title": "How to use them",
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
        "lic_subject": "Vos codes de licence VoiceGuide AirLink",
        "lic_title": "Voici vos 3 visites offertes",
        "lic_intro": "Merci pour votre inscription ! Voici vos codes de licence. Ils n'expirent pas : utilisez-les quand vous voulez.",
        "guests": "Jusqu'à {n} participants",
        "how_title": "Comment les utiliser",
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
        "lic_subject": "Tus códigos de licencia de VoiceGuide AirLink",
        "lic_title": "Aquí tienes tus 3 tours gratuitos",
        "lic_intro": "¡Gracias por registrarte! Estos son tus códigos de licencia. No caducan: úsalos cuando quieras.",
        "guests": "Hasta {n} participantes",
        "how_title": "Cómo usarlos",
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
        "lic_subject": "Ihre Lizenzcodes für VoiceGuide AirLink",
        "lic_title": "Hier sind Ihre 3 Gratis-Touren",
        "lic_intro": "Danke für Ihre Registrierung! Das sind Ihre Lizenzcodes. Sie verfallen nicht: Nutzen Sie sie, wann Sie wollen.",
        "guests": "Bis zu {n} Gäste",
        "how_title": "So nutzen Sie sie",
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
    """Contenitore comune (app/email_layout.py)."""
    return layout(title, inner_html, lang)


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
    steps = "".join(f"<li style=\"margin:0 0 6px;\">{escape(s)}</li>" for s in STEPS[lang])

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
    text_lines += [f"{i}. {s}" for i, s in enumerate(STEPS[lang], 1)]
    text_lines += ["", t["notes"], "", f"App Store: {APP_STORE_URL}", f"Google Play: {PLAY_STORE_URL}", "", t["help"], WHATSAPP_URL, "", t["signoff"]]

    _send_email(
        to_email=to_email,
        subject=t["lic_subject"],
        text_body="\n".join(text_lines),
        html_body=_layout(t["lic_title"], inner, lang),
    )


# ---------------------------------------------------------------------------
# Promemoria a 7 giorni (app/free_tours_reminders.py): solo a chi non ha
# ancora usato nessuno dei 3 codici. Testo neutro: niente "gratis" in oggetto.
# ---------------------------------------------------------------------------
REMINDER = {
    "it": {
        "subject": "I tuoi 3 tour VoiceGuide ti aspettano",
        "title": "I tuoi 3 tour ti aspettano",
        "intro": "Qualche giorno fa hai ricevuto i tuoi codici VoiceGuide AirLink, ma non li hai ancora usati. Nessuna fretta: non scadono.",
        "video": "Guarda come funziona (30 secondi)",
        "codes": "I tuoi codici",
        "tip_title": "Un consiglio per iniziare",
        "tip": "Fai una prova a casa con un amico: tu sei la guida, lui l'ospite. Usa il codice da 5 ospiti: bastano due telefoni e 5 minuti.",
        "help": "Qualcosa non ti è chiaro? Rispondi a questa email: ti risponde una persona del team.",
        "unsub": "Non vuoi ricevere altri promemoria?",
        "unsub_link": "Disiscriviti",
    },
    "en": {
        "subject": "Your 3 VoiceGuide tours are waiting",
        "title": "Your 3 tours are waiting",
        "intro": "A few days ago you received your VoiceGuide AirLink codes, but you haven't used them yet. No rush: they never expire.",
        "video": "Watch how it works (30 seconds)",
        "codes": "Your codes",
        "tip_title": "A tip to get started",
        "tip": "Try it at home with a friend: you're the guide, they're the guest. Use the 5-guest code: all you need is two phones and 5 minutes.",
        "help": "Anything unclear? Just reply to this email: a real person from our team will answer.",
        "unsub": "Don't want any more reminders?",
        "unsub_link": "Unsubscribe",
    },
    "fr": {
        "subject": "Vos 3 visites VoiceGuide vous attendent",
        "title": "Vos 3 visites vous attendent",
        "intro": "Il y a quelques jours, vous avez reçu vos codes VoiceGuide AirLink, mais vous ne les avez pas encore utilisés. Rien ne presse : ils n'expirent pas.",
        "video": "Voir comment ça marche (30 secondes)",
        "codes": "Vos codes",
        "tip_title": "Un conseil pour commencer",
        "tip": "Faites un essai chez vous avec un ami : vous êtes le guide, il est l'invité. Utilisez le code 5 participants : deux téléphones et 5 minutes suffisent.",
        "help": "Quelque chose n'est pas clair ? Répondez simplement à cet e-mail : une vraie personne de l'équipe vous répondra.",
        "unsub": "Vous ne voulez plus recevoir de rappels ?",
        "unsub_link": "Se désinscrire",
    },
    "es": {
        "subject": "Tus 3 tours de VoiceGuide te esperan",
        "title": "Tus 3 tours te esperan",
        "intro": "Hace unos días recibiste tus códigos de VoiceGuide AirLink, pero todavía no los has usado. Sin prisa: no caducan.",
        "video": "Mira cómo funciona (30 segundos)",
        "codes": "Tus códigos",
        "tip_title": "Un consejo para empezar",
        "tip": "Haz una prueba en casa con un amigo: tú eres el guía y él, el invitado. Usa el código de 5 participantes: bastan dos teléfonos y 5 minutos.",
        "help": "¿Algo no está claro? Responde a este email: te contestará una persona del equipo.",
        "unsub": "¿No quieres recibir más recordatorios?",
        "unsub_link": "Darte de baja",
    },
    "de": {
        "subject": "Ihre 3 VoiceGuide-Touren warten auf Sie",
        "title": "Ihre 3 Touren warten auf Sie",
        "intro": "Vor ein paar Tagen haben Sie Ihre Codes für VoiceGuide AirLink erhalten, sie aber noch nicht genutzt. Keine Eile: Sie verfallen nicht.",
        "video": "So funktioniert es (30 Sekunden)",
        "codes": "Ihre Codes",
        "tip_title": "Ein Tipp für den Anfang",
        "tip": "Probieren Sie es zu Hause mit einem Freund aus: Sie sind der Guide, er ist der Gast. Nehmen Sie den Code für 5 Gäste: Zwei Handys und 5 Minuten genügen.",
        "help": "Ist etwas unklar? Antworten Sie einfach auf diese E-Mail: Es antwortet Ihnen ein Mensch aus unserem Team.",
        "unsub": "Sie möchten keine Erinnerungen mehr?",
        "unsub_link": "Abmelden",
    },
}


def build_free_tours_reminder_email(
    licenses: list[tuple[str, int]],
    language: str,
    unsubscribe_url: str,
) -> tuple[str, str, str]:
    """(oggetto, testo, html) del promemoria; separato dall'invio per l'anteprima."""
    lang, t = _t(language)
    r = REMINDER[lang]
    video_url = f"{SITE_URL}/video/spot-{lang}.mp4"
    poster_url = f"{SITE_URL}/video/spot-{lang}.jpg"

    rows = "".join(
        f"""<tr>
          <td style="padding:10px 12px;border-bottom:1px solid #F1EBDD;font-size:18px;font-weight:bold;letter-spacing:1px;">{escape(code)}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #F1EBDD;font-size:14px;color:#4A4F5A;text-align:right;white-space:nowrap;">{escape(t["guests"].format(n=n))}</td>
        </tr>"""
        for code, n in licenses
    )
    steps = "".join(f"<li style=\"margin:0 0 6px;\">{escape(s)}</li>" for s in STEPS[lang])

    inner = f"""
      <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4A4F5A;">{escape(r["intro"])}</p>
      <div style="text-align:center;margin:0 0 22px;">
        <a href="{video_url}" style="text-decoration:none;color:#14161B;">
          <img src="{poster_url}" alt="{escape(r["video"])}" width="180" style="width:180px;height:auto;border:0;border-radius:16px;display:block;margin:0 auto 10px;">
          <span style="display:inline-block;background:#FFC226;color:#14161B;font-weight:bold;font-size:14px;padding:11px 18px;border-radius:999px;">&#9654; {escape(r["video"])}</span>
        </a>
      </div>
      <p style="margin:0 0 8px;font-size:15px;font-weight:bold;">{escape(r["codes"])}</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#FFF8E6;border:2px solid #F2C94C;border-radius:14px;margin:0 0 20px;">
        {rows}
      </table>
      <p style="margin:0 0 6px;font-size:15px;font-weight:bold;">{escape(r["tip_title"])}</p>
      <p style="margin:0 0 18px;font-size:14px;line-height:1.55;color:#4A4F5A;">{escape(r["tip"])}</p>
      <p style="margin:0 0 8px;font-size:15px;font-weight:bold;">{escape(t["how_title"])}</p>
      <ol style="margin:0 0 18px;padding-left:20px;font-size:14px;line-height:1.55;color:#2A2E36;">{steps}</ol>
      <p style="margin:0 0 20px;">
        <a href="{APP_STORE_URL}" style="display:inline-block;background:#14161B;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 18px;border-radius:999px;margin:0 6px 6px 0;">App Store</a>
        <a href="{PLAY_STORE_URL}" style="display:inline-block;background:#14161B;color:#FFFFFF;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 18px;border-radius:999px;margin:0 6px 6px 0;">Google Play</a>
      </p>
      <p style="margin:0 0 20px;font-size:14px;line-height:1.55;color:#4A4F5A;">{escape(r["help"])}</p>
      <p style="margin:0 0 20px;font-size:14px;color:#14161B;">{escape(t["signoff"])}</p>
      <p style="margin:0;font-size:12px;line-height:1.5;color:#8A8F99;">{escape(r["unsub"])} <a href="{escape(unsubscribe_url)}" style="color:#8A8F99;">{escape(r["unsub_link"])}</a></p>
    """
    text_lines = [r["title"], "", r["intro"], "", f"{r['video']}: {video_url}", "", r["codes"]]
    text_lines += [f"{code} — {t['guests'].format(n=n)}" for code, n in licenses]
    text_lines += ["", r["tip_title"], r["tip"], "", t["how_title"]]
    text_lines += [f"{i}. {s}" for i, s in enumerate(STEPS[lang], 1)]
    text_lines += ["", f"App Store: {APP_STORE_URL}", f"Google Play: {PLAY_STORE_URL}", "", r["help"], "", t["signoff"]]
    text_lines += ["", f"{r['unsub']} {unsubscribe_url}"]

    return r["subject"], "\n".join(text_lines), _layout(r["title"], inner, lang)


def send_free_tours_reminder_email(
    to_email: str,
    licenses: list[tuple[str, int]],
    language: str,
    unsubscribe_url: str,
) -> None:
    subject, text, html = build_free_tours_reminder_email(licenses, language, unsubscribe_url)
    _send_email(
        to_email=to_email,
        subject=subject,
        text_body=text,
        html_body=html,
        headers={
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


# ---------------------------------------------------------------------------
# Email 2 giorni dopo il primo codice usato (app/free_tours_reminders.py):
# com'e' andata + prezzi, senza sconti (decisione di Stefano, 2026-10-23).
# ---------------------------------------------------------------------------
FOLLOWUP = {
    "it": {
        "subject": "Com'è andato il tuo tour con VoiceGuide?",
        "title": "Com'è andato il tour?",
        "intro": "Qualche giorno fa hai usato il tuo primo codice VoiceGuide AirLink. Speriamo che il gruppo ti abbia sentito forte e chiaro!",
        "ask": "Ci racconti com'è andata? Basta rispondere a questa email, anche con due righe: le leggiamo tutte e ci aiutano a migliorare l'app.",
        "remaining": "Ti restano ancora questi codici:",
        "pricing": "Quando ti serviranno altri tour, li compri uno alla volta, senza abbonamento: €3,99 fino a 5 ospiti, €14,99 fino a 25. Se fai tour spesso, con il pacchetto da 5 tour (25 ospiti) ogni tour costa €12.",
        "unsub": "Non vuoi ricevere altre email come questa?",
    },
    "en": {
        "subject": "How did your VoiceGuide tour go?",
        "title": "How did the tour go?",
        "intro": "A few days ago you used your first VoiceGuide AirLink code. We hope your group heard you loud and clear!",
        "ask": "Will you tell us how it went? Just reply to this email, even with a couple of lines: we read every reply and it helps us improve the app.",
        "remaining": "You still have these codes:",
        "pricing": "When you need more tours, buy them one at a time, no subscription: €3.99 for up to 5 guests, €14.99 for up to 25. If you guide often, with the 5-tour pack (25 guests) each tour costs €12.",
        "unsub": "Don't want any more emails like this?",
    },
    "fr": {
        "subject": "Comment s'est passée votre visite avec VoiceGuide ?",
        "title": "Comment s'est passée la visite ?",
        "intro": "Il y a quelques jours, vous avez utilisé votre premier code VoiceGuide AirLink. Nous espérons que votre groupe vous a entendu haut et clair !",
        "ask": "Vous nous racontez comment ça s'est passé ? Il suffit de répondre à cet e-mail, même en deux lignes : nous lisons toutes les réponses et elles nous aident à améliorer l'application.",
        "remaining": "Il vous reste encore ces codes :",
        "pricing": "Quand il vous faudra d'autres visites, achetez-les une à la fois, sans abonnement : 3,99 € jusqu'à 5 participants, 14,99 € jusqu'à 25. Si vous guidez souvent, avec le pack 5 visites (25 participants), chaque visite revient à 12 €.",
        "unsub": "Vous ne voulez plus recevoir d'e-mails comme celui-ci ?",
    },
    "es": {
        "subject": "¿Qué tal fue tu tour con VoiceGuide?",
        "title": "¿Qué tal fue el tour?",
        "intro": "Hace unos días usaste tu primer código de VoiceGuide AirLink. ¡Esperamos que tu grupo te haya oído alto y claro!",
        "ask": "¿Nos cuentas qué tal fue? Basta con responder a este email, aunque sea con dos líneas: leemos todas las respuestas y nos ayudan a mejorar la app.",
        "remaining": "Todavía te quedan estos códigos:",
        "pricing": "Cuando necesites más tours, cómpralos de uno en uno, sin suscripción: 3,99 € hasta 5 participantes, 14,99 € hasta 25. Si haces tours a menudo, con el pack de 5 tours (25 participantes) cada tour sale a 12 €.",
        "unsub": "¿No quieres recibir más emails como este?",
    },
    "de": {
        "subject": "Wie war Ihre Tour mit VoiceGuide?",
        "title": "Wie war die Tour?",
        "intro": "Vor ein paar Tagen haben Sie Ihren ersten Code für VoiceGuide AirLink genutzt. Wir hoffen, Ihre Gruppe hat Sie laut und deutlich gehört!",
        "ask": "Erzählen Sie uns, wie es war? Antworten Sie einfach auf diese E-Mail, gern auch in zwei Zeilen: Wir lesen jede Antwort, und sie hilft uns, die App zu verbessern.",
        "remaining": "Diese Codes haben Sie noch:",
        "pricing": "Wenn Sie weitere Touren brauchen, kaufen Sie sie einzeln, ohne Abo: 3,99 € bis 5 Gäste, 14,99 € bis 25. Wenn Sie oft führen, kostet mit dem 5-Touren-Paket (25 Gäste) jede Tour 12 €.",
        "unsub": "Sie möchten keine solchen E-Mails mehr?",
    },
}


def build_free_tours_followup_email(
    remaining: list[tuple[str, int]],
    language: str,
    unsubscribe_url: str,
) -> tuple[str, str, str]:
    """(oggetto, testo, html); remaining = codici non ancora usati (anche vuoto)."""
    lang, t = _t(language)
    f = FOLLOWUP[lang]
    pricing_url = f"{SITE_URL}/{lang}#prezzi"

    codes_html = ""
    if remaining:
        rows = "".join(
            f"""<tr>
          <td style="padding:10px 12px;border-bottom:1px solid #F1EBDD;font-size:18px;font-weight:bold;letter-spacing:1px;">{escape(code)}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #F1EBDD;font-size:14px;color:#4A4F5A;text-align:right;white-space:nowrap;">{escape(t["guests"].format(n=n))}</td>
        </tr>"""
            for code, n in remaining
        )
        codes_html = f"""
      <p style="margin:0 0 8px;font-size:15px;font-weight:bold;">{escape(f["remaining"])}</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#FFF8E6;border:2px solid #F2C94C;border-radius:14px;margin:0 0 20px;">
        {rows}
      </table>"""

    unsub = REMINDER[lang]["unsub_link"]
    inner = f"""
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#4A4F5A;">{escape(f["intro"])}</p>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#14161B;font-weight:bold;">{escape(f["ask"])}</p>
      {codes_html}
      <p style="margin:0 0 16px;font-size:14px;line-height:1.55;color:#4A4F5A;">{escape(f["pricing"])}</p>
      <p style="margin:0 0 22px;">
        <a href="{pricing_url}" style="display:inline-block;background:#FFC226;color:#14161B;text-decoration:none;font-weight:bold;font-size:14px;padding:12px 20px;border-radius:999px;">{escape(t["buy"])} →</a>
      </p>
      <p style="margin:0 0 20px;font-size:14px;color:#14161B;">{escape(t["signoff"])}</p>
      <p style="margin:0;font-size:12px;line-height:1.5;color:#8A8F99;">{escape(f["unsub"])} <a href="{escape(unsubscribe_url)}" style="color:#8A8F99;">{escape(unsub)}</a></p>
    """
    text_lines = [f["title"], "", f["intro"], "", f["ask"], ""]
    if remaining:
        text_lines += [f["remaining"]] + [f"{code} — {t['guests'].format(n=n)}" for code, n in remaining] + [""]
    text_lines += [f["pricing"], f"{t['buy']}: {pricing_url}", "", t["signoff"], "", f"{f['unsub']} {unsubscribe_url}"]

    return f["subject"], "\n".join(text_lines), _layout(f["title"], inner, lang)


def send_free_tours_followup_email(
    to_email: str,
    remaining: list[tuple[str, int]],
    language: str,
    unsubscribe_url: str,
) -> None:
    subject, text, html = build_free_tours_followup_email(remaining, language, unsubscribe_url)
    _send_email(
        to_email=to_email,
        subject=subject,
        text_body=text,
        html_body=html,
        headers={
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )
