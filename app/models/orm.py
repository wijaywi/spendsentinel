"""SQLAlchemy ORM models for SpendSentinel."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ValidationLog(Base):
    """Log record of pre-transaction validation requests and outcomes."""

    __tablename__ = "validation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    request_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class AgentProfile(Base):
    """Autonomous agent registered under Agent Guard."""

    __tablename__ = "agent_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    transactions: Mapped[list["AgentTransaction"]] = relationship(
        "AgentTransaction", back_populates="agent", cascade="all, delete-orphan"
    )


class AgentTransaction(Base):
    """Transactions executed by registered autonomous agents."""

    __tablename__ = "agent_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("agent_profiles.agent_id"), nullable=False, index=True
    )
    merchant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_violations_json: Mapped[list[Any]] = mapped_column(
        JSON, default=list, nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    agent: Mapped["AgentProfile"] = relationship(
        "AgentProfile", back_populates="transactions"
    )


class EvidenceRecord(Base):
    """Complete evidence artifact stored for transaction protection."""

    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    order_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    device_fingerprint_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    shipping_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    customer_history_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    payment_details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DisputeResponse(Base):
    """Dispute auto-response package and defense recommendations."""

    __tablename__ = "dispute_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispute_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )
    evidence_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(20), nullable=False)
    auto_submitted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )


class AuditLog(Base):
    """Central audit log for all security actions across Sentinel modules."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
