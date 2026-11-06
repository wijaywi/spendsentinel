"""Database models for AI Agent Commerce Guard."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy import Boolean, DateTime, Float, Index, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone information."""
    return datetime.now(timezone.utc)


class AgentProfileModel(Base):
    """SQLAlchemy model representing an authorized AI agent profile."""

    __tablename__ = "guard_agent_profiles"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    max_transaction_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    daily_spending_limit: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    budget_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )
    allowed_currencies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_merchants: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    requires_human_approval_above: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 6), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AgentTransactionModel(Base):
    """SQLAlchemy model representing evaluated agent transactions."""

    __tablename__ = "guard_agent_transactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    merchant_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    category_mcc: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    violations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    review_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )

    __table_args__ = (
        Index(
            "uq_guard_agent_idempotency",
            "agent_id",
            "idempotency_key",
            unique=True,
        ),
        Index("ix_guard_agent_created", "agent_id", "created_at"),
        Index("ix_guard_agent_decision", "agent_id", "decision"),
    )
