# models/trial_requests.py

from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
import enum

from models import Base


class TrialRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    ISSUED = "ISSUED"
    REJECTED = "REJECTED"


class TrialRequest(Base):
    __tablename__ = "trial_requests"

    id = Column(Integer, primary_key=True, index=True)

    # Dati richiedente
    name = Column(String, nullable=True)
    email = Column(String, nullable=False, index=True)
    language = Column(String, nullable=False, default="it")  # it / en

    # Messaggio / note
    message = Column(String, nullable=True)

    # Stato gestione admin
    status = Column(
        Enum(TrialRequestStatus, name="trial_request_status"),
        nullable=False,
        default=TrialRequestStatus.PENDING,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
