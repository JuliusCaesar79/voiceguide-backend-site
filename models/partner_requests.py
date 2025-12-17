# models/partner_requests.py

from sqlalchemy import Column, Integer, String, DateTime, Enum, text
from sqlalchemy.sql import func
import enum

from models import Base


class PartnerTier(str, enum.Enum):
    BASE = "BASE"
    PRO = "PRO"
    ELITE = "ELITE"


class PartnerRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PartnerRequest(Base):
    __tablename__ = "partner_requests"

    # PK: niente index=True (già indicizzato)
    id = Column(Integer, primary_key=True)

    name = Column(String(255), nullable=False)

    # unique + index (l'index viene creato automaticamente dal unique)
    email = Column(String(255), nullable=False, index=True, unique=True)

    partner_tier = Column(
        Enum(PartnerTier, name="partner_tier"),
        nullable=False,
        server_default=text("'BASE'"),
    )

    notes = Column(String(1000), nullable=True)

    # Index su status: utile per dashboard admin
    status = Column(
        Enum(PartnerRequestStatus, name="partner_request_status"),
        nullable=False,
        server_default=text("'PENDING'"),
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
