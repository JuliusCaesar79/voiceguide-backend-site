from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, Enum
from sqlalchemy.sql import func
import enum

from models import Base


class PackageType(str, enum.Enum):
    SINGLE = "SINGLE"       # Licenze singole per guide
    TO = "TO"               # Pacchetti Tour Operator
    SCHOOL = "SCHOOL"       # Pacchetti scuole
    MUSEUM = "MUSEUM"       # Eventuale uso musei/partner speciali


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)

    package_type = Column(Enum(PackageType), nullable=False)

    # Quante licenze genera il pacchetto (es. 10×25 ospiti → num_licenses = 10)
    num_licenses = Column(Integer, nullable=False, default=1)

    # Capienza massima per singola licenza del pacchetto
    max_guests = Column(Integer, nullable=False)

    # Prezzo totale del pacchetto
    price = Column(Numeric(10, 2), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
