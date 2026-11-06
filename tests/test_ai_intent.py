import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app.config import settings
from app.schemas.agent import AgentDecision, AgentDecisionEnum, AgentIntentExtraction
from app.services.ai_intent import AIIntentClient


def test_ai_client_extracts_structured_intent_from_configured_provider(monkeypatch) -> None:
    from app.services import ai_intent

    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_API_URL", "https://ai.example/v1/chat/completions")
    monkeypatch.setattr(settings, "AI_ALLOWED_HOSTS", ["ai.example"])
    monkeypatch.setattr(settings, "AI_MODEL", "test-model")
    real_client = httpx.AsyncClient
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["authorization"] = request.headers.get("authorization")
        observed["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '```json\n{"amount":"24.50","currency":"USD",'
                                '"merchant_name":"Office Supply",'
                                '"category_mcc":"5943",'
                                '"description":"Purchase printer paper"}\n```'
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        ai_intent.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    extracted = asyncio.run(
        AIIntentClient().extract("Buy printer paper for $24.50 at Office Supply")
    )

    assert extracted == AgentIntentExtraction(
        amount="24.50",
        currency="USD",
        merchant_name="Office Supply",
        category_mcc="5943",
        description="Purchase printer paper",
    )
    assert observed["authorization"] == "Bearer test-key"
    assert '"temperature":0' in observed["body"]


def test_ai_client_rejects_unallowlisted_remote_host(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_API_URL", "https://untrusted.example/chat")
    monkeypatch.setattr(settings, "AI_ALLOWED_HOSTS", ["ai.example"])

    with pytest.raises(HTTPException) as error:
        asyncio.run(AIIntentClient().extract("Buy a desk lamp for $18"))
    assert error.value.status_code == 503


def test_ai_client_fails_closed_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_ENABLED", False)
    monkeypatch.setattr(settings, "AI_API_KEY", None)
    with pytest.raises(HTTPException) as error:
        asyncio.run(AIIntentClient().extract("Buy a desk lamp for $18"))
    assert error.value.status_code == 503


def test_local_lm_studio_does_not_require_api_key(monkeypatch) -> None:
    from app.services import ai_intent

    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", None)
    monkeypatch.setattr(
        settings,
        "AI_API_URL",
        "http://127.0.0.1:1234/v1/chat/completions",
    )
    monkeypatch.setattr(settings, "AI_MODEL", "local-test-model")
    real_client = httpx.AsyncClient
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["authorization"] = request.headers.get("authorization")
        observed["model"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"amount":"18.00","currency":"USD",'
                                '"merchant_name":null,"category_mcc":null,'
                                '"description":"Desk lamp"}'
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        ai_intent.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    extracted = asyncio.run(AIIntentClient().extract("Buy desk lamp for $18"))
    assert extracted.amount == "18.00"
    assert observed["authorization"] is None
    assert '"model":"local-test-model"' in observed["model"]


def test_natural_language_route_applies_guard_after_ai_extraction(monkeypatch) -> None:
    from app.api.agents import get_agent_guard
    from app.main import app

    extracted = AgentIntentExtraction(
        amount="24.50",
        currency="USD",
        merchant_name="Office Supply",
        category_mcc="5943",
        description="Purchase printer paper",
    )
    decision = AgentDecision(
        decision=AgentDecisionEnum.APPROVE,
        agent_id="demo_agent",
        transaction_id="tx-123",
        idempotency_key="ai-intent-key",
        amount="24.50",
        currency="USD",
        risk_score=5,
        evaluated_at="2026-11-03T00:00:00Z",
    )
    observed = {}

    class FakeAIClient:
        async def extract(self, instruction):
            observed["instruction"] = instruction
            return extracted

    class FakeGuard:
        async def evaluate_transaction(self, transaction):
            observed["transaction"] = transaction
            return decision

    monkeypatch.setattr("app.api.agents.AIIntentClient", FakeAIClient)
    app.dependency_overrides[get_agent_guard] = lambda: FakeGuard()

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.post(
                "/api/agents/interpret-and-evaluate",
                json={
                    "idempotency_key": "ai-intent-key",
                    "agent_id": "demo_agent",
                    "merchant_id": "merchant-trusted-id",
                    "instruction": "Buy printer paper for $24.50",
                },
            )

    try:
        response = asyncio.run(request())
    finally:
        app.dependency_overrides.pop(get_agent_guard, None)

    assert response.status_code == 200, response.text
    assert response.json()["ai_model"] == settings.AI_MODEL
    assert response.json()["decision"]["decision"] == "APPROVE"
    assert observed["transaction"].merchant_id == "merchant-trusted-id"
    assert str(observed["transaction"].amount) == "24.50"
