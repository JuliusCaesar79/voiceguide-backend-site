from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.sql import func

from models import Base


class PartnerPayout(Base):
    __tablename__ = "partner_payouts"

    id = Column(Integer, primary_key=True, index=True)

    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)

    # Commissione spettante su quell’ordine
    amount = Column(Numeric(10, 2), nullable=False)

    # Se è stata già pagata o meno
    paid = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
