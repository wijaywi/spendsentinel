"""FastAPI router for SpendSentinel dashboard and monitoring metrics."""

from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, text

from app.core.database import get_db
from app.models.evidence import (
    EvidenceRecordModel,
    DisputeResponseModel,
    AuditActivityModel,
    ValidationRecordModel,
    AgentTransactionModel,
    CorridorRiskModel,
)
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    ValidationSummary,
    AgentTransactionSummary,
    EvidenceDisputeSummary,
    RiskScoreDistribution,
    RecentActivityItem,
    CorridorRiskItem,
)
from app.security import require_scopes

router = APIRouter(prefix="/api/dashboard", tags=["Sentinel Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:read")),
) -> DashboardSummaryResponse:
    """Retrieve unified executive dashboard summary across all Sentinel protection pillars.

    Aggregates:
    1. Pre-Transaction Validations (pass/warn/block counts)
    2. Autonomous Agent Security Decisions (approve/deny/escalate counts)
    3. Evidence Vault & Dispute Shield Metrics (evidence stored, contest/escalate/accept counts)
    4. System-wide risk score distribution
    """
    try:
        # 1. Validation counts (PFPE)
        validations_query = db.query(ValidationRecordModel).all()
        new_validation_rows = db.execute(
            text("SELECT status, risk_score FROM prevalidation_logs")
        ).all()
        val_statuses = [v.status.upper() for v in validations_query]
        val_statuses.extend(row.status.upper() for row in new_validation_rows)
        val_pass = sum(1 for current in val_statuses if current == "PASS")
        val_warn = sum(1 for current in val_statuses if current == "WARN")
        val_block = sum(1 for current in val_statuses if current == "BLOCK")
        val_total = len(val_statuses)

        # 2. Agent transaction counts (ACSO)
        agent_tx_query = db.query(AgentTransactionModel).all()
        new_agent_rows = db.execute(
            text("SELECT decision, risk_score FROM guard_agent_transactions")
        ).all()
        agent_decisions = [a.decision.upper() for a in agent_tx_query]
        agent_decisions.extend(row.decision.upper() for row in new_agent_rows)
        ag_approve = sum(1 for current in agent_decisions if current == "APPROVE")
        ag_deny = sum(1 for current in agent_decisions if current == "DENY")
        ag_escalate = sum(1 for current in agent_decisions if current == "ESCALATE")
        ag_total = len(agent_decisions)

        # 3. Evidence and Dispute response counts (DPS)
        total_evidence_records = db.query(EvidenceRecordModel).count()
        dispute_responses = db.query(DisputeResponseModel).all()
        total_dispute_responses = len(dispute_responses)
        auto_contested = sum(1 for d in dispute_responses if d.recommended_action == "CONTEST")
        dr_escalated = sum(1 for d in dispute_responses if d.recommended_action == "ESCALATE")
        dr_accepted = sum(1 for d in dispute_responses if d.recommended_action == "ACCEPT")

        # 4. Risk score distribution
        # Bucket scores from validations and disputes
        risk_scores: List[int] = []
        for v in validations_query:
            risk_scores.append(v.risk_score)
        risk_scores.extend(row.risk_score for row in new_validation_rows)
        risk_scores.extend(row.risk_score for row in new_agent_rows)
        for d in dispute_responses:
            # Invert dispute defense confidence to risk (high confidence = low risk)
            risk_scores.append(max(0, 100 - d.confidence_score))

        low_risk = sum(1 for s in risk_scores if 0 <= s <= 30)
        med_risk = sum(1 for s in risk_scores if 31 <= s <= 60)
        high_risk = sum(1 for s in risk_scores if 61 <= s <= 80)
        crit_risk = sum(1 for s in risk_scores if s > 80)

        # If empty initial state, set baseline distributions for demo
        if not risk_scores:
            low_risk, med_risk, high_risk, crit_risk = 0, 0, 0, 0

        return DashboardSummaryResponse(
            validations=ValidationSummary(
                total=val_total,
                pass_count=val_pass,
                warn_count=val_warn,
                block_count=val_block,
            ),
            agent_transactions=AgentTransactionSummary(
                total=ag_total,
                approve_count=ag_approve,
                deny_count=ag_deny,
                escalate_count=ag_escalate,
            ),
            evidence_disputes=EvidenceDisputeSummary(
                total_evidence_records=total_evidence_records,
                total_dispute_responses=total_dispute_responses,
                auto_contested=auto_contested,
                escalated=dr_escalated,
                accepted=dr_accepted,
            ),
            risk_score_distribution=RiskScoreDistribution(
                low=low_risk,
                medium=med_risk,
                high=high_risk,
                critical=crit_risk,
            ),
            system_status="OPERATIONAL",
            last_updated=datetime.utcnow(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate dashboard summary: {str(exc)}",
        )


@router.get("/recent-activity", response_model=List[RecentActivityItem])
def get_recent_activity(
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:read")),
) -> List[RecentActivityItem]:
    """Retrieve the last 20 audit events across all SpendSentinel modules.

    Chronologically ordered events covering Evidence Vault storage, Dispute defense,
    pre-transaction validation results, and AI agent policy enforcements.
    """
    activities = (
        db.query(AuditActivityModel)
        .order_by(desc(AuditActivityModel.timestamp))
        .limit(20)
        .all()
    )
    return [
        RecentActivityItem(
            id=act.id,
            module=act.module,
            event_type=act.event_type,
            severity=act.severity,
            reference_id=act.reference_id,
            summary=act.summary,
            details=act.details,
            timestamp=act.timestamp,
        )
        for act in activities
    ]


@router.get("/risk-heatmap", response_model=List[CorridorRiskItem])
def get_risk_heatmap(
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:read")),
) -> List[CorridorRiskItem]:
    """Retrieve cross-border payment corridor risk data for geographical visualization.

    Returns international transaction corridors with failure rates, dispute rates,
    network latency, and risk status indicators.
    """
    corridors = (
        db.query(CorridorRiskModel)
        .order_by(desc(CorridorRiskModel.risk_score))
        .all()
    )
    return [
        CorridorRiskItem(
            id=c.id,
            source_country=c.source_country,
            target_country=c.target_country,
            corridor_code=c.corridor_code,
            transaction_volume=c.transaction_volume,
            failure_rate=c.failure_rate,
            dispute_rate=c.dispute_rate,
            avg_latency_ms=c.avg_latency_ms,
            risk_score=c.risk_score,
            status=c.status,
            updated_at=c.updated_at,
        )
        for c in corridors
    ]
