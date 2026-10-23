# routers/free_tours_unsubscribe.py
"""
Disiscrizione dai promemoria dei tour gratuiti (link in fondo all'email).

GET  /free-tours/unsubscribe?id=&t=&lang=  -> pagina con il pulsante di conferma
POST /free-tours/unsubscribe?id=&t=&lang=  -> disiscrive (anche il "one-click"
                                              dei programmi di posta)
Il GET non disiscrive da solo: alcuni filtri antispam aprono i link delle email.
"""
import hmac
from datetime import datetime, timezone
from html import escape

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.db import SessionLocal
from app.email_layout import SITE_URL, norm_lang
from app.free_tours_reminders import unsubscribe_token
from models.free_tour_signups import FreeTourSignup

router = APIRouter(prefix="/free-tours", tags=["Free tours"])

TEXTS = {
    "it": {"ask": "Non vuoi più ricevere promemoria da VoiceGuide AirLink?", "button": "Sì, disiscrivimi", "done": "Fatto: non riceverai altri promemoria. I tuoi codici restano validi.", "bad": "Link non valido."},
    "en": {"ask": "Don't want any more reminders from VoiceGuide AirLink?", "button": "Yes, unsubscribe me", "done": "Done: you won't receive any more reminders. Your codes stay valid.", "bad": "Invalid link."},
    "fr": {"ask": "Vous ne voulez plus recevoir de rappels de VoiceGuide AirLink ?", "button": "Oui, me désinscrire", "done": "C'est fait : vous ne recevrez plus de rappels. Vos codes restent valables.", "bad": "Lien non valide."},
    "es": {"ask": "¿No quieres recibir más recordatorios de VoiceGuide AirLink?", "button": "Sí, darme de baja", "done": "Listo: no recibirás más recordatorios. Tus códigos siguen siendo válidos.", "bad": "Enlace no válido."},
    "de": {"ask": "Sie möchten keine Erinnerungen von VoiceGuide AirLink mehr erhalten?", "button": "Ja, abmelden", "done": "Erledigt: Sie erhalten keine Erinnerungen mehr. Ihre Codes bleiben gültig.", "bad": "Ungültiger Link."},
}


def _page(lang: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>VoiceGuide AirLink</title></head>
<body style="margin:0;background:#FBF8F1;font-family:Arial,Helvetica,sans-serif;color:#14161B;">
<div style="max-width:480px;margin:60px auto;padding:0 16px;text-align:center;">
<a href="{SITE_URL}/{lang}"><img src="{SITE_URL}/brand/voiceguide-airlink-logo.png" alt="VoiceGuide AirLink" width="130"></a>
<div style="background:#fff;border:1px solid #EEE7D6;border-radius:22px;padding:28px;margin-top:18px;">{body}</div>
</div></body></html>"""
    )


def _valid(signup_id: int, token: str) -> bool:
    return hmac.compare_digest(unsubscribe_token(signup_id), token or "")


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_page(id: int = Query(...), t: str = Query(""), lang: str = Query("it")):
    lang = norm_lang(lang)
    tx = TEXTS[lang]
    if not _valid(id, t):
        return _page(lang, f"<p>{escape(tx['bad'])}</p>")
    action = f"/free-tours/unsubscribe?id={id}&amp;t={escape(t)}&amp;lang={lang}"
    return _page(
        lang,
        f"""<p style="font-size:16px;line-height:1.5;margin:0 0 20px;">{escape(tx['ask'])}</p>
<form method="post" action="{action}"><button type="submit" style="background:#FFC226;border:0;border-radius:999px;padding:12px 22px;font-size:15px;font-weight:bold;cursor:pointer;">{escape(tx['button'])}</button></form>""",
    )


@router.post("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(id: int = Query(...), t: str = Query(""), lang: str = Query("it")):
    lang = norm_lang(lang)
    tx = TEXTS[lang]
    if not _valid(id, t):
        return _page(lang, f"<p>{escape(tx['bad'])}</p>")
    db = SessionLocal()
    try:
        row = db.get(FreeTourSignup, id)
        if row and row.emails_opt_out_at is None:
            row.emails_opt_out_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
    return _page(lang, f"<p style=\"font-size:16px;line-height:1.5;margin:0;\">{escape(tx['done'])}</p>")
