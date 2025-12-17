# models/partner_payments.py

from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String
from sqlalchemy.sql import func

from models import Base


class PartnerPayment(Base):
    """
    Pagamento REALE effettuato al partner (bonifico / contanti / saldo).
    NON è legato a un singolo ordine.
    Serve per tenere separati:
    - Commissioni maturate (PartnerPayout per ordine)
    - Pagamenti effettuati (PartnerPayment)
    """
    __tablename__ = "partner_payments"

    id = Column(Integer, primary_key=True, index=True)

    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)

    note = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
