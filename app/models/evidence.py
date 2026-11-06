"""SQLAlchemy ORM models for Evidence Vault, Disputes, and Sentinel Dashboard."""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    JSON,
    Text,
    UniqueConstraint,
)
from app.core.database import Base


class EvidenceRecordModel(Base):
    """Immutable evidence record for audit-trail compliance."""

    __tablename__ = "evidence_records"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id", "version", name="uq_evidence_transaction_version"
        ),
    )

    id = Column(String(64), primary_key=True, index=True)
    transaction_id = Column(String(64), index=True, nullable=False)
    customer_id = Column(String(64), index=True, nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="USD")
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Device & Network Fingerprint
    device_fingerprint = Column(JSON, nullable=True)
    device_id = Column(String(128), index=True, nullable=True)
    ip_address = Column(String(64), index=True, nullable=True)

    # Addresses & Verification
    shipping_address = Column(JSON, nullable=True)
    billing_address = Column(JSON, nullable=True)
    billing_address_verified = Column(Boolean, default=False, nullable=False)

    # Fulfillment Proof
    delivery_tracking_number = Column(String(128), nullable=True)
    delivery_carrier = Column(String(64), nullable=True)
    delivery_status = Column(String(64), nullable=True)
    delivery_confirmed = Column(Boolean, default=False, nullable=False)

    # Item details
    item_description = Column(Text, nullable=True)

    # Scoring & Audit Trail
    evidence_strength = Column(Integer, default=0, nullable=False)
    strength_breakdown = Column(JSON, nullable=True)
    prior_successful_transactions_count = Column(Integer, default=0, nullable=False)

    # Append-only versioning
    parent_record_id = Column(String(64), nullable=True, index=True)
    version = Column(Integer, default=1, nullable=False)
    extra_metadata = Column(JSON, nullable=True)


class DisputeResponseModel(Base):
    """Auto-response and evidence package generated for PayPal disputes."""

    __tablename__ = "dispute_responses"

    id = Column(String(64), primary_key=True, index=True)
    dispute_id = Column(String(64), index=True, nullable=False)
    transaction_id = Column(String(64), index=True, nullable=False)
    confidence_score = Column(Integer, nullable=False)
    recommended_action = Column(String(32), nullable=False)  # CONTEST, ESCALATE, ACCEPT
    action_reason = Column(Text, nullable=False)
    evidence_package = Column(JSON, nullable=False)
    ce3_compliance = Column(JSON, nullable=False)
    status = Column(String(32), default="GENERATED", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditActivityModel(Base):
    """System-wide audit activity event log across all SpendSentinel modules."""

    __tablename__ = "audit_activity_logs"

    id = Column(String(64), primary_key=True, index=True)
    module = Column(String(64), index=True, nullable=False)
    event_type = Column(String(64), index=True, nullable=False)
    severity = Column(String(32), default="INFO", nullable=False)
    reference_id = Column(String(128), nullable=True, index=True)
    summary = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ValidationRecordModel(Base):
    """Pre-transaction validation log record (PFPE module)."""

    __tablename__ = "validation_records"

    id = Column(String(64), primary_key=True, index=True)
    transaction_id = Column(String(64), index=True, nullable=False)
    corridor = Column(String(32), nullable=True)
    rule_name = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)  # PASS, WARN, BLOCK
    risk_score = Column(Integer, default=0, nullable=False)
    message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class AgentTransactionModel(Base):
    """Autonomous AI agent transaction log record (ACSO module)."""

    __tablename__ = "agent_transactions"

    id = Column(String(64), primary_key=True, index=True)
    agent_id = Column(String(64), index=True, nullable=False)
    transaction_id = Column(String(64), index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    decision = Column(String(32), nullable=False)  # APPROVE, DENY, ESCALATE
    policy_checked = Column(String(128), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class CorridorRiskModel(Base):
    """International corridor risk model for cross-border visualization."""

    __tablename__ = "corridor_risks"

    id = Column(String(64), primary_key=True, index=True)
    source_country = Column(String(8), nullable=False)
    target_country = Column(String(8), nullable=False)
    corridor_code = Column(String(16), unique=True, index=True, nullable=False)
    transaction_volume = Column(Integer, default=0, nullable=False)
    failure_rate = Column(Float, default=0.0, nullable=False)
    dispute_rate = Column(Float, default=0.0, nullable=False)
    avg_latency_ms = Column(Integer, default=150, nullable=False)
    risk_score = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="LOW_RISK", nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
