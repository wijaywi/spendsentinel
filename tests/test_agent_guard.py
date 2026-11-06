import asyncio
from decimal import Decimal

import pytest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.database import Base
from app.schemas.agent import AgentRegistration, AgentTransactionRequest
from app.services.agent_guard import AgentGuard


def _request(key: str, amount: float = 8.0, currency: str = "USD", description: str = "service") -> AgentTransactionRequest:
    return AgentTransactionRequest(
        idempotency_key=key,
        agent_id="agent_demo",
        amount=amount,
        currency=currency,
        merchant_id="merchant_demo",
        description=description,
    )


def _run_with_db(tmp_path, operation):
    async def run():
        db_file = tmp_path / "agent-test.db"
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_file}",
            connect_args={"timeout": 15},
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await operation(factory)
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_idempotency_binds_description_and_replays_identical_result(tmp_path) -> None:
    async def operation(factory):
        async with factory() as db:
            guard = AgentGuard(db)
            await guard.register_agent(
                AgentRegistration(
                    agent_id="agent_demo",
                    name="Demo",
                    owner_id="owner_demo",
                    max_transaction_amount=50,
                    daily_spending_limit=100,
                    allowed_currencies=["USD"],
                )
            )
            first = await guard.evaluate_transaction(_request("request-1"))
            replay = await guard.evaluate_transaction(_request("request-1"))
            altered = await guard.evaluate_transaction(
                _request("request-1", description="different service")
            )

        assert first.decision.value == "APPROVE"
        assert replay.cached is True
        assert altered.decision.value == "DENY"
        assert any("IDEMPOTENCY_CONFLICT" in reason for reason in altered.violations)

    _run_with_db(tmp_path, operation)


def test_non_budget_currency_is_denied_without_trusted_exchange_rate(tmp_path) -> None:
    async def operation(factory):
        async with factory() as db:
            guard = AgentGuard(db)
            await guard.register_agent(
                AgentRegistration(
                    agent_id="agent_demo",
                    name="Demo",
                    owner_id="owner_demo",
                    max_transaction_amount=50,
                    daily_spending_limit=100,
                    allowed_currencies=["USD", "EUR"],
                    budget_currency="USD",
                )
            )
            result = await guard.evaluate_transaction(
                _request("request-eur", amount=10, currency="EUR")
            )
            spending = await guard.get_agent_spending("agent_demo")

        assert result.decision.value == "DENY"
        assert any("CURRENCY_CONVERSION_UNAVAILABLE" in item for item in result.violations)
        assert spending["total_spent"] == 0
        assert spending["budget_currency"] == "USD"

    _run_with_db(tmp_path, operation)


def test_concurrent_requests_cannot_overrun_daily_limit(tmp_path) -> None:
    async def operation(factory):
        async with factory() as db:
            await AgentGuard(db).register_agent(
                AgentRegistration(
                    agent_id="agent_demo",
                    name="Demo",
                    owner_id="owner_demo",
                    max_transaction_amount=10,
                    daily_spending_limit=10,
                    allowed_currencies=["USD"],
                )
            )

        async def evaluate(key: str):
            async with factory() as db:
                return await AgentGuard(db).evaluate_transaction(_request(key))

        first, second = await asyncio.gather(
            evaluate("concurrent-1"), evaluate("concurrent-2")
        )
        decisions = sorted([first.decision.value, second.decision.value])
        assert decisions == ["APPROVE", "DENY"]

    _run_with_db(tmp_path, operation)


def test_decimal_budget_boundary_is_not_affected_by_float_rounding(tmp_path) -> None:
    async def operation(factory):
        async with factory() as db:
            await AgentGuard(db).register_agent(
                AgentRegistration(
                    agent_id="agent_demo",
                    name="Demo",
                    owner_id="owner_demo",
                    max_transaction_amount=Decimal("0.10"),
                    daily_spending_limit=Decimal("0.30"),
                    allowed_currencies=["USD"],
                )
            )

        async with factory() as db:
            guard = AgentGuard(db)
            results = [
                await guard.evaluate_transaction(
                    _request(f"decimal-{index}", amount=Decimal("0.10"))
                )
                for index in range(3)
            ]
            final = await guard.evaluate_transaction(
                _request("decimal-over", amount=Decimal("0.10"))
            )

        assert all(result.decision.value == "APPROVE" for result in results)
        assert final.decision.value == "DENY"

    _run_with_db(tmp_path, operation)


def test_agent_amount_obeys_currency_minor_units() -> None:
    with pytest.raises(ValueError, match="decimal places"):
        _request("bad-precision", amount=Decimal("1.001"))
