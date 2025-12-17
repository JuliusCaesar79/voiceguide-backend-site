from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, Boolean
from sqlalchemy.sql import func
import enum

from models import Base


class PartnerType(str, enum.Enum):
    BASE = "BASE"
    PRO = "PRO"
    ELITE = "ELITE"


class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False, unique=True)

    partner_type = Column(Enum(PartnerType), nullable=False, default=PartnerType.BASE)

    # Percentuale di commissione (es. 12, 18, 25)
    commission_pct = Column(Numeric(5, 2), nullable=False)

    # Codice referral del partner (es. VG-ROMA-001)
    referral_code = Column(String(100), nullable=False, unique=True)

    notes = Column(String(1000), nullable=True)

    # In futuro potremo marcare partner attivo/disattivato
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
