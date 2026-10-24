# app/customer_emails.py
"""
Email ai clienti nello stile nuovo, in 5 lingue (restyle 2026-10):
- ordine ricevuto (pagamento in attesa);
- pagamento confermato, con i codici licenza;
- licenza di prova assegnata dall'admin.
"""
import re

from app.email_layout import (
    SITE_URL,
    button,
    codes_box,
    details,
    footer_text,
    guests_block,
    guests_text,
    layout,
    norm_lang,
    p,
    signoff,
    steps_block,
    steps_text,
    store_buttons,
)
from app.email_service import _send_email

LABELS = {
    "it": {"single": "Licenza singola · fino a {g} ospiti", "to": "Pacchetto Tour Operator · {n} licenze da {g} ospiti", "bundle": "5 Tour · {g} ospiti", "school": "Pacchetto Scuole · {n} licenze da {g} ospiti", "guests": "Fino a {g} ospiti"},
    "en": {"single": "Single license · up to {g} guests", "to": "Tour Operator pack · {n} licenses for {g} guests", "bundle": "5 Tours · {g} guests", "school": "Schools pack · {n} licenses for {g} guests", "guests": "Up to {g} guests"},
    "fr": {"single": "Licence à l'unité · jusqu'à {g} participants", "to": "Pack Tour-opérateur · {n} licences de {g} participants", "bundle": "5 Visites · {g} participants", "school": "Pack Écoles · {n} licences de {g} participants", "guests": "Jusqu'à {g} participants"},
    "es": {"single": "Licencia individual · hasta {g} participantes", "to": "Paquete Touroperador · {n} licencias de {g} participantes", "bundle": "5 Tours · {g} participantes", "school": "Paquete Colegios · {n} licencias de {g} participantes", "guests": "Hasta {g} participantes"},
    "de": {"single": "Einzellizenz · bis zu {g} Gäste", "to": "Reiseveranstalter-Paket · {n} Lizenzen für {g} Gäste", "bundle": "5 Touren · {g} Gäste", "school": "Schulen-Paket · {n} Lizenzen für {g} Gäste", "guests": "Bis zu {g} Gäste"},
}


def product_label(product: str | None, lang: str) -> str | None:
    """SINGLE_25, PACKAGE_TO_10 / PACKAGE_TO_10x25, PACKAGE_BUNDLE5_35, PACKAGE_SCHOOL_5 → testo leggibile."""
    if not product:
        return None
    code = product.strip().upper()
    L = LABELS[lang]
    if m := re.fullmatch(r"SINGLE_(\d+)", code):
        return L["single"].format(g=m.group(1))
    if m := re.fullmatch(r"PACKAGE_BUNDLE5_(\d+)", code):
        return L["bundle"].format(g=m.group(1))
    if m := re.fullmatch(r"PACKAGE_TO_(\d+)(?:X(\d+))?", code):
        n, g = m.group(1), m.group(2) or "25"
        if n == "5":  # i "5 Tour" usano package_type TO con 5 licenze
            return L["bundle"].format(g=g)
        return L["to"].format(n=n, g=g)
    if m := re.fullmatch(r"PACKAGE_SCHOOL_(\d+)(?:X(\d+))?", code):
        return L["school"].format(n=m.group(1), g=m.group(2) or "100")
    return product


def _eur(lang: str, amount: float) -> str:
    v = f"{amount:.2f}"
    return f"€{v}" if lang == "en" else (f"€{v.replace('.', ',')}" if lang == "it" else f"{v.replace('.', ',')} €")


ORDER_RECEIVED = {
    "it": {"subject": "Ordine ricevuto · VoiceGuide AirLink", "title": "Abbiamo ricevuto il tuo ordine", "intro": "Grazie! Ecco il riepilogo. Appena il pagamento è confermato ti mandiamo un'altra email con i codici licenza.",
           "order": "Ordine", "product": "Prodotto", "subtotal": "Subtotale", "discount": "Sconto partner", "total": "Totale", "invoice": "Fattura", "yes": "Sì", "no": "No", "status": "Pagamento", "pending": "In attesa"},
    "en": {"subject": "Order received · VoiceGuide AirLink", "title": "We've received your order", "intro": "Thank you! Here's your summary. As soon as the payment is confirmed we'll send you another email with your license codes.",
           "order": "Order", "product": "Product", "subtotal": "Subtotal", "discount": "Partner discount", "total": "Total", "invoice": "Invoice", "yes": "Yes", "no": "No", "status": "Payment", "pending": "Pending"},
    "fr": {"subject": "Commande reçue · VoiceGuide AirLink", "title": "Nous avons bien reçu votre commande", "intro": "Merci ! Voici le récapitulatif. Dès que le paiement est confirmé, nous vous envoyons un autre e-mail avec vos codes de licence.",
           "order": "Commande", "product": "Produit", "subtotal": "Sous-total", "discount": "Remise partenaire", "total": "Total", "invoice": "Facture", "yes": "Oui", "no": "Non", "status": "Paiement", "pending": "En attente"},
    "es": {"subject": "Pedido recibido · VoiceGuide AirLink", "title": "Hemos recibido tu pedido", "intro": "¡Gracias! Aquí tienes el resumen. En cuanto se confirme el pago te enviaremos otro email con tus códigos de licencia.",
           "order": "Pedido", "product": "Producto", "subtotal": "Subtotal", "discount": "Descuento partner", "total": "Total", "invoice": "Factura", "yes": "Sí", "no": "No", "status": "Pago", "pending": "Pendiente"},
    "de": {"subject": "Bestellung erhalten · VoiceGuide AirLink", "title": "Wir haben Ihre Bestellung erhalten", "intro": "Vielen Dank! Hier ist die Übersicht. Sobald die Zahlung bestätigt ist, senden wir Ihnen eine weitere E-Mail mit Ihren Lizenzcodes.",
           "order": "Bestellung", "product": "Produkt", "subtotal": "Zwischensumme", "discount": "Partnerrabatt", "total": "Gesamt", "invoice": "Rechnung", "yes": "Ja", "no": "Nein", "status": "Zahlung", "pending": "Ausstehend"},
}


def send_order_received(
    to_email: str,
    order_id: int,
    product: str,
    total_amount: float,
    discount_amount: float = 0.0,
    invoice_requested: bool = False,
    intestatario: str | None = None,
    language: str = "en",
) -> None:
    lang = norm_lang(language)
    t = ORDER_RECEIVED[lang]
    rows = [(t["order"], f"#{order_id}"), (t["product"], product_label(product, lang) or product)]
    if discount_amount and discount_amount > 0:
        rows += [(t["subtotal"], _eur(lang, total_amount + discount_amount)), (t["discount"], "-" + _eur(lang, discount_amount))]
    rows.append((t["total"], _eur(lang, total_amount)))
    inv = t["yes"] + (f" ({intestatario})" if intestatario else "") if invoice_requested else t["no"]
    rows += [(t["invoice"], inv), (t["status"], t["pending"])]

    inner = p(t["intro"]) + details(rows) + signoff(lang)
    text = [t["title"], "", t["intro"], ""] + [f"{k}: {v}" for k, v in rows] + footer_text(lang)
    _send_email(to_email=to_email, subject=t["subject"], text_body="\n".join(text), html_body=layout(t["title"], inner, lang))


PAYMENT = {
    "it": {"subject": "Pagamento confermato: ecco i tuoi codici · VoiceGuide AirLink", "title": "Pagamento confermato", "intro": "Grazie per l'acquisto! Ecco i tuoi codici licenza. Non scadono: usali quando vuoi.",
           "order": "Ordine", "product": "Prodotto", "multi": "Ogni codice vale per un tour. Le licenze non sono nominative: puoi darle alle guide del tuo team.",
           "one": "Le licenze non sono nominative: puoi passarle a un collega.", "note": "Ogni licenza vale per un tour fino a 4 ore, che partono quando inserisci il codice nell'app.", "code": "Codice"},
    "en": {"subject": "Payment confirmed: here are your codes · VoiceGuide AirLink", "title": "Payment confirmed", "intro": "Thanks for your purchase! Here are your license codes. They never expire: use them whenever you like.",
           "order": "Order", "product": "Product", "multi": "Each code covers one tour. Licenses aren't tied to a person: you can give them to the guides on your team.",
           "one": "Licenses aren't tied to a person: you can pass them to a colleague.", "note": "Each license covers one tour of up to 4 hours, starting when you enter the code in the app.", "code": "Code"},
    "fr": {"subject": "Paiement confirmé : voici vos codes · VoiceGuide AirLink", "title": "Paiement confirmé", "intro": "Merci pour votre achat ! Voici vos codes de licence. Ils n'expirent pas : utilisez-les quand vous voulez.",
           "order": "Commande", "product": "Produit", "multi": "Chaque code vaut pour une visite. Les licences ne sont pas nominatives : vous pouvez les donner aux guides de votre équipe.",
           "one": "Les licences ne sont pas nominatives : vous pouvez les transmettre à un collègue.", "note": "Chaque licence vaut pour une visite jusqu'à 4 heures, qui commencent quand vous saisissez le code dans l'application.", "code": "Code"},
    "es": {"subject": "Pago confirmado: aquí tienes tus códigos · VoiceGuide AirLink", "title": "Pago confirmado", "intro": "¡Gracias por tu compra! Aquí tienes tus códigos de licencia. No caducan: úsalos cuando quieras.",
           "order": "Pedido", "product": "Producto", "multi": "Cada código vale para un tour. Las licencias no son nominativas: puedes dárselas a los guías de tu equipo.",
           "one": "Las licencias no son nominativas: puedes pasárselas a un compañero.", "note": "Cada licencia vale para un tour de hasta 4 horas, que empiezan cuando introduces el código en la app.", "code": "Código"},
    "de": {"subject": "Zahlung bestätigt: Ihre Codes · VoiceGuide AirLink", "title": "Zahlung bestätigt", "intro": "Vielen Dank für Ihren Kauf! Hier sind Ihre Lizenzcodes. Sie verfallen nicht: Nutzen Sie sie, wann Sie wollen.",
           "order": "Bestellung", "product": "Produkt", "multi": "Jeder Code gilt für eine Tour. Die Lizenzen sind nicht personengebunden: Sie können sie an die Guides Ihres Teams weitergeben.",
           "one": "Die Lizenzen sind nicht personengebunden: Sie können sie an Kollegen weitergeben.", "note": "Jede Lizenz gilt für eine Tour bis zu 4 Stunden, die ab der Eingabe des Codes in der App laufen.", "code": "Code"},
}


def send_payment_confirmed(
    to_email: str,
    order_id: int,
    product: str | None,
    codes: list[str],
    language: str = "en",
) -> None:
    lang = norm_lang(language)
    t = PAYMENT[lang]
    label = product_label(product, lang)
    rows = [(t["order"], f"#{order_id}")] + ([(t["product"], label)] if label else [])
    multi = len(codes) > 1
    code_rows = [(c, f"{t['code']} {i}/{len(codes)}" if multi else "") for i, c in enumerate(codes, 1)]

    inner = (
        p(t["intro"])
        + details(rows)
        + (codes_box(code_rows) if codes else "")
        + steps_block(lang)
        + store_buttons()
        + guests_block(lang)
        + p(t["multi"] if multi else t["one"], muted=True)
        + p(t["note"], muted=True)
        + signoff(lang)
    )
    text = [t["title"], "", t["intro"], ""] + [f"{k}: {v}" for k, v in rows] + [""] + codes + [""] + steps_text(lang) + guests_text(lang) + ["", t["multi"] if multi else t["one"], t["note"]] + footer_text(lang)
    _send_email(to_email=to_email, subject=t["subject"], text_body="\n".join(text), html_body=layout(t["title"], inner, lang))


TRIAL = {
    "it": {"subject": "La tua licenza di prova · VoiceGuide AirLink", "title": "Ecco la tua licenza di prova", "hello": "Ciao {name}!", "intro": "Grazie per voler provare VoiceGuide AirLink. Ecco il tuo codice: non scade, usalo quando vuoi.", "buy": "Vedi i prezzi"},
    "en": {"subject": "Your trial license · VoiceGuide AirLink", "title": "Here's your trial license", "hello": "Hi {name}!", "intro": "Thanks for trying VoiceGuide AirLink. Here's your code: it never expires, use it whenever you like.", "buy": "See pricing"},
    "fr": {"subject": "Votre licence d'essai · VoiceGuide AirLink", "title": "Voici votre licence d'essai", "hello": "Bonjour {name} !", "intro": "Merci d'essayer VoiceGuide AirLink. Voici votre code : il n'expire pas, utilisez-le quand vous voulez.", "buy": "Voir les tarifs"},
    "es": {"subject": "Tu licencia de prueba · VoiceGuide AirLink", "title": "Aquí tienes tu licencia de prueba", "hello": "¡Hola {name}!", "intro": "Gracias por probar VoiceGuide AirLink. Aquí tienes tu código: no caduca, úsalo cuando quieras.", "buy": "Ver precios"},
    "de": {"subject": "Ihre Testlizenz · VoiceGuide AirLink", "title": "Hier ist Ihre Testlizenz", "hello": "Hallo {name}!", "intro": "Danke, dass Sie VoiceGuide AirLink testen. Hier ist Ihr Code: Er verfällt nicht, nutzen Sie ihn, wann Sie wollen.", "buy": "Preise ansehen"},
}


def send_trial_license(to_email: str, license_code: str, max_guests: int, name: str | None = None, language: str = "en") -> None:
    lang = norm_lang(language)
    t = TRIAL[lang]
    hello = t["hello"].format(name=name.strip()) if name and name.strip() else ""
    guests = LABELS[lang]["guests"].format(g=max_guests)
    inner = (
        (p(hello) if hello else "")
        + p(t["intro"])
        + codes_box([(license_code, guests)])
        + steps_block(lang)
        + store_buttons()
        + guests_block(lang)
        + button(t["buy"], f"{SITE_URL}/{lang}#prezzi")
        + signoff(lang)
    )
    text = ([hello, ""] if hello else []) + [t["intro"], "", f"{license_code} — {guests}", ""] + steps_text(lang) + guests_text(lang) + footer_text(lang)
    _send_email(to_email=to_email, subject=t["subject"], text_body="\n".join(text), html_body=layout(t["title"], inner, lang))
