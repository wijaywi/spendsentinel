"""Pydantic schemas for SpendSentinel dashboard metrics, activity, and corridor risk."""

from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


class ValidationSummary(BaseModel):
    """Validation outcome counts from Pre-Transaction Validation (PFPE)."""

    total: int = 0
    pass_count: int = Field(0, serialization_alias="pass")
    warn_count: int = Field(0, serialization_alias="warn")
    block_count: int = Field(0, serialization_alias="block")

    class Config:
        populate_by_name = True


class AgentTransactionSummary(BaseModel):
    """Agentic transaction policy decision counts (ACSO)."""

    total: int = 0
    approve_count: int = Field(0, serialization_alias="approve")
    deny_count: int = Field(0, serialization_alias="deny")
    escalate_count: int = Field(0, serialization_alias="escalate")

    class Config:
        populate_by_name = True


class EvidenceDisputeSummary(BaseModel):
    """Evidence vault and dispute prevention summary (DPS)."""

    total_evidence_records: int = 0
    total_dispute_responses: int = 0
    auto_contested: int = 0
    escalated: int = 0
    accepted: int = 0


class RiskScoreDistribution(BaseModel):
    """System-wide risk score bucket distribution."""

    low: int = 0       # 0 - 30
    medium: int = 0    # 31 - 60
    high: int = 0      # 61 - 80
    critical: int = 0  # 81 - 100


class DashboardSummaryResponse(BaseModel):
    """Unified system summary across pre-validation, AI agents, and dispute prevention."""

    validations: ValidationSummary
    agent_transactions: AgentTransactionSummary
    evidence_disputes: EvidenceDisputeSummary
    risk_score_distribution: RiskScoreDistribution
    system_status: str = "OPERATIONAL"
    last_updated: datetime


class RecentActivityItem(BaseModel):
    """Recent event log entry across all SpendSentinel modules."""

    id: str
    module: str
    event_type: str
    severity: str
    reference_id: Optional[str] = None
    summary: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class CorridorRiskItem(BaseModel):
    """Cross-border corridor risk profile."""

    id: str
    source_country: str
    target_country: str
    corridor_code: str
    transaction_volume: int
    failure_rate: float
    dispute_rate: float
    avg_latency_ms: int
    risk_score: int
    status: str
    updated_at: datetime

    class Config:
        from_attributes = True
