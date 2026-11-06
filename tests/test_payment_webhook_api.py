import json

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core import database as core_database
from app.main import app
from app.models.payment_event import PayPalWebhookEvent


def test_paypal_webhook_route_verifies_then_deduplicates_event(monkeypatch, tmp_path) -> None:
    db_engine = create_engine(f"sqlite:///{tmp_path / 'webhooks.db'}")
    core_database.Base.metadata.create_all(db_engine)
    test_sessions = sessionmaker(bind=db_engine)

    def override_get_db():
        with test_sessions() as session:
            yield session

    app.dependency_overrides[core_database.get_db] = override_get_db
    monkeypatch.setattr(settings, "PAYPAL_SANDBOX_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "PAYPAL_API_BASE_URL",
        "https://api-m.sandbox.paypal.com",
    )
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-secret")
    monkeypatch.setattr(settings, "PAYPAL_WEBHOOK_ID", "WEBHOOK-123")

    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "sandbox-access"})
        return httpx.Response(200, json={"verification_status": "SUCCESS"})

    monkeypatch.setattr(
        "app.services.paypal_api.httpx.AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )

    headers = {
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-cert-url": "https://api-m.sandbox.paypal.com/cert",
        "paypal-transmission-id": "transmission-123",
        "paypal-transmission-sig": "signature",
        "paypal-transmission-time": "2026-11-03T00:00:00Z",
    }
    event = {"id": "WH-EVENT-API-1", "event_type": "CHECKOUT.ORDER.APPROVED"}
    client = TestClient(app)
    try:
        first = client.post(
            "/api/payments/webhooks/paypal",
            headers=headers,
            content=json.dumps(event),
        )
        replay = client.post(
            "/api/payments/webhooks/paypal",
            headers=headers,
            content=json.dumps(event),
        )
        assert first.status_code == 200, first.text
        assert first.json()["duplicate"] is False
        assert replay.status_code == 200, replay.text
        assert replay.json()["duplicate"] is True
        with test_sessions() as session:
            assert session.query(PayPalWebhookEvent).count() == 1
    finally:
        app.dependency_overrides.pop(core_database.get_db, None)
        db_engine.dispose()
