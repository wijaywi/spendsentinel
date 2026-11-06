from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.agent import AgentProfile, AgentTransactionRequest
from app.services import risk_engine


def test_agent_risk_ignores_client_supplied_hour_and_velocity(monkeypatch) -> None:
    class FixedDateTime:
        @staticmethod
        def now(_tz):
            return datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(risk_engine, "datetime", FixedDateTime)
    profile = AgentProfile(
        agent_id="agent-1",
        name="Agent",
        owner_id="owner-1",
        status="ACTIVE",
        max_transaction_amount=Decimal("100"),
        daily_spending_limit=Decimal("100"),
        allowed_currencies=["USD"],
        allowed_merchants=[],
        allowed_categories=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    ordinary = AgentTransactionRequest(
        idempotency_key="ordinary",
        agent_id="agent-1",
        amount=Decimal("10"),
        currency="USD",
        merchant_id="merchant-1",
        metadata={},
    )
    spoofed = ordinary.model_copy(
        update={"metadata": {"hour": 2, "velocity": "not-an-integer"}}
    )

    assert risk_engine.calculate_agent_risk(profile, ordinary) == 5
    assert risk_engine.calculate_agent_risk(profile, spoofed) == 5
