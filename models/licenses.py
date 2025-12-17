from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Text,
)
from sqlalchemy.sql import func
import enum

from models import Base


class LicenseType(str, enum.Enum):
    SINGLE = "SINGLE"
    TO = "TO"
    SCHOOL = "SCHOOL"
    MUSEUM = "MUSEUM"


class License(Base):
    __tablename__ = "licenses"

    # PK: niente index=True (già indicizzato)
    id = Column(Integer, primary_key=True)

    # Unique basta e avanza (in Postgres crea già l'indice)
    code = Column(String(100), nullable=False, unique=True)

    license_type = Column(Enum(LicenseType), nullable=False)

    max_guests = Column(Integer, nullable=False)

    duration_hours = Column(Integer, nullable=False, default=4)

    activated_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    is_expired = Column(Boolean, nullable=False, default=False)

    activated_by_guide = Column(String(255), nullable=True)

    # email destinatario (utile per trial/manual e storico invii)
    issued_to_email = Column(String(255), nullable=True, index=True)

    notes = Column(Text, nullable=True)

    issued_by_admin = Column(String(255), nullable=True)

    # per trial/manual può essere NULL
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
