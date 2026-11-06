"""Audit log model for SpendSentinel compliance and tracking."""

import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone information."""
    return datetime.now(timezone.utc)


class AuditLogModel(Base):
    """SQLAlchemy model for persisting secure audit trail events."""

    __tablename__ = "guard_audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    agent_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )

    __table_args__ = (
        Index("ix_guard_audit_agent_created", "agent_id", "created_at"),
    )
