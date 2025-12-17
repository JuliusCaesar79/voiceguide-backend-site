# models/order_billing_details.py

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import relationship

from models import Base


class OrderBillingDetails(Base):
    __tablename__ = "order_billing_details"

    id = Column(Integer, primary_key=True)

    # FK -> orders.id
    # unique=True crea già un indice/vincolo sufficiente: non serve index=True
    order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    request_invoice = Column(Boolean, nullable=False, server_default=text("false"))

    country = Column(String(2), nullable=True)  # ISO2 es: IT, FR, DE
    company_name = Column(String(255), nullable=True)

    vat_number = Column(String(32), nullable=True)
    tax_code = Column(String(32), nullable=True)

    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    zip_code = Column(String(20), nullable=True)
    province = Column(String(50), nullable=True)

    pec = Column(String(255), nullable=True)
    sdi_code = Column(String(16), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    order = relationship("Order", back_populates="billing_details")
