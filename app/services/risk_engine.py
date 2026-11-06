"""Risk scoring engine for deterministic AI-agent transaction policy checks."""

from datetime import datetime, timezone
from typing import Optional
from app.schemas.agent import AgentProfile, AgentTransactionRequest


def calculate_agent_risk(
    agent: AgentProfile,
    transaction: AgentTransactionRequest,
    recent_velocity: int = 0,
    is_new_merchant: bool = False,
    historical_merchants: Optional[list[str]] = None,
) -> float:
    """Calculate merchant-side risk score (0-100) for an AI agent transaction.

    Factors evaluated:
    1. Spending velocity (recent transactions per minute)
    2. Transaction size relative to agent limits
    3. Merchant familiarity and allowlist status
    4. Unusual currency deviation from primary currency
    5. Unusual transaction timing (off-peak UTC hours)

    Args:
        agent: Agent profile containing spending policy parameters.
        transaction: Inbound agent transaction request.
        recent_velocity: Number of transactions evaluated in the last 60 seconds.
        is_new_merchant: Whether the target merchant is newly encountered.
        historical_merchants: Optional list of previously transacted merchant IDs.

    Returns:
        float: Composite risk score bounded between 0.0 and 100.0.
    """
    risk_score = 5.0

    # 1. Spending velocity factor
    metadata = transaction.metadata or {}
    velocity = max(0, recent_velocity)
    if velocity >= 9:
        risk_score += 35.0
    elif velocity >= 6:
        risk_score += 25.0
    elif velocity >= 3:
        risk_score += 15.0
    elif velocity >= 1:
        risk_score += 5.0

    # 2. Transaction size relative to limit
    if agent.max_transaction_amount > 0:
        ratio = transaction.amount / agent.max_transaction_amount
        if ratio > 0.95:
            risk_score += 28.0
        elif ratio > 0.80:
            risk_score += 20.0
        elif ratio > 0.50:
            risk_score += 10.0
        elif ratio > 0.20:
            risk_score += 4.0

    # 3. Merchant familiarity factor
    merchant_id = transaction.merchant_id
    if agent.allowed_merchants:
        if merchant_id not in agent.allowed_merchants:
            risk_score += 30.0
    else:
        is_new = (
            is_new_merchant
            or bool(metadata.get("is_new_merchant", False))
            or (
                historical_merchants is not None
                and merchant_id not in historical_merchants
            )
        )
        if is_new:
            risk_score += 15.0

    # 4. Unusual currency factor
    req_currency = transaction.currency.strip().upper()
    allowed_upper = [c.upper() for c in agent.allowed_currencies]
    if req_currency not in allowed_upper:
        risk_score += 25.0
    elif allowed_upper and req_currency != allowed_upper[0]:
        risk_score += 10.0

    # 5. Unusual timing factor (off-peak hours: 01:00-05:00 UTC)
    current_hour = datetime.now(timezone.utc).hour
    if 1 <= current_hour <= 5:
        risk_score += 10.0

    return round(min(100.0, max(0.0, risk_score)), 2)
