# app/email_guard.py
"""
Controlli anti-abuso per la registrazione gratuita (3 tour):
- normalize_email: stessa casella scritta in modi diversi conta una volta sola
  (minuscole, senza "+tag", e per Gmail senza punti nella parte locale);
- is_disposable: domini di caselle usa e getta piu' diffusi.
"""

GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}

# Elenco dei domini usa e getta piu' comuni. Non e' completo: serve a fermare
# i casi facili, le registrazioni restano comunque visibili nella dashboard.
DISPOSABLE_DOMAINS = {
    "10minutemail.com", "10minutemail.net", "20minutemail.com", "33mail.com",
    "anonaddy.me", "burnermail.io", "byom.de", "dispostable.com", "discard.email",
    "dropmail.me", "emailondeck.com", "emailfake.com", "fakeinbox.com", "fakemail.net",
    "getairmail.com", "getnada.com", "guerrillamail.biz", "guerrillamail.com",
    "guerrillamail.de", "guerrillamail.info", "guerrillamail.net", "guerrillamail.org",
    "guerrillamailblock.com", "harakirimail.com", "inboxbear.com", "incognitomail.org",
    "jetable.org", "linshiyouxiang.net", "mail-temp.com", "mail.tm", "mailcatch.com",
    "maildrop.cc", "mailinator.com", "mailinator.net", "mailinator2.com", "mailnesia.com",
    "mailpoof.com", "mailsac.com", "mintemail.com", "mohmal.com", "moakt.com",
    "mytemp.email", "nada.email", "sharklasers.com", "spam4.me", "spamgourmet.com",
    "spambox.us", "temp-mail.io", "temp-mail.org", "tempail.com", "tempinbox.com",
    "tempmail.com", "tempmail.dev", "tempmail.net", "tempmail.plus", "tempmailo.com",
    "tempr.email", "throwawaymail.com", "trashmail.com", "trashmail.de", "trashmail.net",
    "tmail.ws", "tmpmail.net", "tmpmail.org", "wegwerfmail.de", "wegwerfmail.net",
    "yopmail.com", "yopmail.fr", "yopmail.net", "cool.fr.nf", "jetable.fr.nf",
    "courriel.fr.nf", "moncourrier.fr.nf", "monemail.fr.nf", "monmail.fr.nf",
    "emltmp.com", "minuteinbox.com", "fakemailgenerator.com", "inboxkitten.com",
    "1secmail.com", "1secmail.net", "1secmail.org", "esiix.com", "wwjmp.com",
    "xojxe.com", "yoggm.com", "laafd.com", "vjuum.com", "txcct.com", "rteet.com",
    "dpptd.com", "kzccv.com", "qiott.com", "cuoly.com", "mailto.plus", "fexpost.com",
    "fexbox.org", "mailbox.in.ua", "rover.info", "chitthi.in", "fextemp.com",
    "any.pink", "merepost.com", "spymail.one", "tempmailbox.net",
}


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    local = local.split("+", 1)[0]
    if domain in GMAIL_DOMAINS:
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def is_disposable(email: str) -> bool:
    domain = (email or "").strip().lower().rsplit("@", 1)[-1]
    # copre anche i sottodomini (es. xyz.yopmail.com)
    return any(domain == d or domain.endswith("." + d) for d in DISPOSABLE_DOMAINS)
