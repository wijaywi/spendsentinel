"""
SQLAlchemy model for pre-transaction validation audit logs.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, JSON
from app.database import Base


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class ValidationLog(Base):
    """
    Persistent log record for pre-transaction validation checks.
    Stores comprehensive audit trail of payment evaluations and recommendations.
    """
    __tablename__ = "prevalidation_logs"

    id = Column(String(64), primary_key=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)

    sender_country = Column(String(2), nullable=False)
    recipient_country = Column(String(2), nullable=False)
    recipient_name = Column(String(255), nullable=False, index=True)
    recipient_account = Column(String(64), nullable=True)
    iban = Column(String(34), nullable=True, index=True)
    bic = Column(String(11), nullable=True)
    currency = Column(String(3), nullable=False)
    amount = Column(Float, nullable=False)
    reference = Column(String(255), nullable=False, index=True)

    status = Column(String(10), nullable=False, index=True)  # PASS, WARN, BLOCK
    risk_score = Column(Integer, nullable=False)  # 0 to 100
    passed = Column(Boolean, nullable=False, default=True)

    checks_results = Column(JSON, nullable=False, default=dict)
    recommendations = Column(JSON, nullable=False, default=list)
    execution_time_ms = Column(Float, default=0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert log entity to serializable dictionary."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sender_country": self.sender_country,
            "recipient_country": self.recipient_country,
            "recipient_name": self.recipient_name,
            "recipient_account": self.recipient_account,
            "iban": self.iban,
            "bic": self.bic,
            "currency": self.currency,
            "amount": self.amount,
            "reference": self.reference,
            "status": self.status,
            "risk_score": self.risk_score,
            "passed": self.passed,
            "checks_results": self.checks_results,
            "recommendations": self.recommendations,
            "execution_time_ms": self.execution_time_ms,
        }
