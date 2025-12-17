# models/admin.py

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from . import Base  # Importiamo Base dal package models


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)

    # Email di login dell'admin
    email = Column(String, unique=True, index=True, nullable=False)

    # Password hashata (non in chiaro!)
    hashed_password = Column(String, nullable=False)

    # Flag per eventuale disattivazione account admin
    is_active = Column(Boolean, default=True, nullable=False)

    # Per futuro uso: superadmin vs admin normale
    is_superadmin = Column(Boolean, default=False, nullable=False)

    # Tracciamo quando è stato creato
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
