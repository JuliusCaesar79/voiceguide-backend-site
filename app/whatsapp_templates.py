# app/whatsapp_templates.py
from urllib.parse import quote_plus


def build_whatsapp_message(text: str) -> str:
    """
    Ritorna una stringa pronta per:
    https://wa.me/?text=...
    """
    return quote_plus(text)
