from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Enum,
    ForeignKey,
    text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from models import Base


class OrderType(str, enum.Enum):
    SINGLE = "SINGLE"          # Licenza singola
    PACKAGE_TO = "PACKAGE_TO"  # Pacchetto Tour Operator
    PACKAGE_SCHOOL = "PACKAGE_SCHOOL"  # Pacchetto scuole
    MUSEUM = "MUSEUM"          # Eventuale modalità musei/partnership


class PaymentMethod(str, enum.Enum):
    STRIPE = "STRIPE"
    PAYPAL = "PAYPAL"
    BANK_TRANSFER = "BANK_TRANSFER"
    OTHER = "OTHER"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    buyer_email = Column(String(255), nullable=False)
    buyer_whatsapp = Column(String(50), nullable=True)

    order_type = Column(Enum(OrderType), nullable=False)

    # Riferimento al pacchetto acquistato (può essere null per ordini speciali)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)

    # Quanti pacchetti (es. 10×25 ospiti → quantity=10)
    quantity = Column(Integer, nullable=False, default=1)

    # --- NUOVO: breakdown importi per sconto partner ---
    # Subtotale (listino) prima dello sconto
    subtotal_amount = Column(Numeric(10, 2), nullable=False, server_default=text("0"))

    # Importo sconto applicato (5% se referral valido)
    discount_amount = Column(Numeric(10, 2), nullable=False, server_default=text("0"))
    # --------------------------------------------------

    # Importo totale pagato dal cliente (dopo sconto)
    total_amount = Column(Numeric(10, 2), nullable=False)

    # Costo stimato interno Agora per questo ordine (facoltativo)
    estimated_agora_cost = Column(Numeric(10, 2), nullable=True)

    payment_method = Column(Enum(PaymentMethod), nullable=False)
    payment_status = Column(
        Enum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.PENDING,
    )

    # Collegamento al partner (se presente)
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=True)

    # Codice referral usato (storico puro)
    referral_code = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ==============================
    # RELATIONSHIPS
    # ==============================

    # 1:1 billing details (fatturazione)
    billing_details = relationship(
        "OrderBillingDetails",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
