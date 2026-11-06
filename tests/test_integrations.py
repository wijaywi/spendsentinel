import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings, settings
from app.schemas.integrations import PayPalOrderRequest, SanctionsScreenRequest
from app.services.paypal_api import PAYPAL_SANDBOX_HOST, PayPalSandboxClient
from app.services.sanctions_provider import SanctionsProvider


def test_oidc_jwks_token_validation_and_scope_authorization(monkeypatch) -> None:
    from app import security

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://issuer.example/")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "sentinel-api")
    monkeypatch.setattr(settings, "OIDC_ALGORITHMS", ["RS256"])

    class SigningKey:
        key = private_key.public_key()

    class Jwks:
        def get_signing_key_from_jwt(self, _token):
            return SigningKey()

    monkeypatch.setattr(security, "_jwks_client", lambda: Jwks())
    valid_token = jwt.encode(
        {
            "sub": "merchant-owner",
            "iss": "https://issuer.example/",
            "aud": "sentinel-api",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "scope": "sentinel:agents:manage",
        },
        private_key,
        algorithm="RS256",
    )
    claims = security.decode_access_token(valid_token)
    assert claims["sub"] == "merchant-owner"

    limited = security.require_scopes("sentinel:payments:capture")
    with pytest.raises(HTTPException) as error:
        asyncio.run(limited(principal=claims))
    assert error.value.status_code == 403


def test_production_api_requires_bearer_token(monkeypatch) -> None:
    from app.main import app

    monkeypatch.setattr(settings, "AUTH_ENABLED", True)

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.get("/api/integrations/status")

    response = asyncio.run(request())
    assert response.status_code == 401


def test_unconfigured_external_integrations_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SANCTIONS_SCREENING_ENABLED", False)
    monkeypatch.setattr(settings, "SANCTIONS_API_URL", None)
    monkeypatch.setattr(settings, "SANCTIONS_API_TOKEN", None)
    monkeypatch.setattr(settings, "PAYPAL_SANDBOX_ENABLED", False)
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", None)
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", None)
    from app.main import app

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            status_response = await client.get("/api/integrations/status")
            sanctions_response = await client.post(
                "/api/compliance/screen",
                json={"full_name": "Example Person"},
            )
            payments_response = await client.post(
                "/api/payments/orders",
                json={
                    "amount": "10.00",
                    "currency": "USD",
                    "reference_id": "test-invoice",
                    "request_id": "local-request-001",
                },
            )
            return status_response, sanctions_response, payments_response

    status_response, sanctions_response, payments_response = asyncio.run(request())
    assert status_response.status_code == 200
    assert status_response.json()["sanctions_screening"]["configured"] is False
    assert status_response.json()["paypal"]["configured"] is False
    assert sanctions_response.status_code == 503
    assert payments_response.status_code == 503


def test_production_configuration_rejects_missing_auth_and_insecure_algorithms() -> None:
    with pytest.raises(ValidationError, match="OIDC configuration"):
        Settings(APP_ENV="production", DEBUG=False, AUTH_ENABLED=False)
    with pytest.raises(ValidationError, match="asymmetric"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            AUTH_ENABLED=True,
            OIDC_ISSUER="https://issuer.example/",
            OIDC_AUDIENCE="sentinel",
            OIDC_JWKS_URL="https://issuer.example/jwks",
            OIDC_ALGORITHMS=["HS256"],
            CORS_ORIGINS=["https://app.example"],
        )


def test_sanctions_adapter_fails_closed_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SANCTIONS_SCREENING_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            SanctionsProvider().screen(
                SanctionsScreenRequest(full_name="Example Person")
            )
        )
    assert error.value.status_code == 503


def test_sanctions_adapter_returns_reviewable_normalized_result(monkeypatch) -> None:
    from app.services import sanctions_provider

    monkeypatch.setattr(settings, "SANCTIONS_SCREENING_ENABLED", True)
    monkeypatch.setattr(settings, "SANCTIONS_API_URL", "https://screen.example/screen")
    monkeypatch.setattr(settings, "SANCTIONS_ALLOWED_HOSTS", ["screen.example"])
    monkeypatch.setattr(settings, "SANCTIONS_API_TOKEN", "test-token")
    monkeypatch.setattr(settings, "SANCTIONS_PROVIDER_NAME", "Contracted Provider")
    real_client = httpx.AsyncClient
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["auth"] = request.headers.get("authorization")
        observed["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "status": "CLEAR",
                "checked_at": "2026-11-03T00:00:00Z",
                "source_updated_at": "2026-11-02T00:00:00Z",
                "matches": [],
            },
        )

    monkeypatch.setattr(
        sanctions_provider.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    result = asyncio.run(
        SanctionsProvider().screen(
            SanctionsScreenRequest(full_name="  Example   Person ", country="gb")
        )
    )

    assert result.provider == "Contracted Provider"
    assert result.status.value == "CLEAR"
    assert result.authoritative_decision is False
    assert result.requires_human_review is True
    assert observed["auth"] == "Bearer test-token"
    assert '"full_name":"Example Person"' in observed["body"]


def test_paypal_order_calls_sandbox_with_idempotency_key(monkeypatch) -> None:
    from app.services import paypal_api

    monkeypatch.setattr(paypal_api, "_token_cache", {})
    monkeypatch.setattr(settings, "PAYPAL_SANDBOX_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "PAYPAL_API_BASE_URL",
        f"https://{PAYPAL_SANDBOX_HOST}",
    )
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-secret")
    real_client = httpx.AsyncClient
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200, json={"access_token": "sandbox-access", "expires_in": 3600}
            )
        return httpx.Response(201, json={"id": "ORDER-123", "status": "CREATED"})

    monkeypatch.setattr(
        paypal_api.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    async def create_orders():
        client = PayPalSandboxClient()
        first = await client.create_order(
            PayPalOrderRequest(
                amount="12.34",
                currency="USD",
                reference_id="invoice-1",
                request_id="stable-request-123",
            )
        )
        second = await client.create_order(
            PayPalOrderRequest(
                amount="3.00",
                currency="USD",
                reference_id="invoice-2",
                request_id="stable-request-124",
            )
        )
        return first, second

    result, second_result = asyncio.run(create_orders())

    assert result["id"] == "ORDER-123"
    assert second_result["id"] == "ORDER-123"
    assert requests[1].headers["paypal-request-id"] == "stable-request-123"
    assert requests[1].url.host == PAYPAL_SANDBOX_HOST
    assert requests[1].read()  # The request contains only the synthetic order.
    assert sum(request.url.path == "/v1/oauth2/token" for request in requests) == 1
    assert sum(request.url.path == "/v2/checkout/orders" for request in requests) == 2


def test_paypal_rejects_non_sandbox_host_and_unapproved_capture(monkeypatch) -> None:
    from app.services import paypal_api

    monkeypatch.setattr(paypal_api, "_token_cache", {})
    monkeypatch.setattr(settings, "PAYPAL_SANDBOX_ENABLED", True)
    monkeypatch.setattr(settings, "PAYPAL_API_BASE_URL", "https://api-m.paypal.com")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "client")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "secret")
    with pytest.raises(HTTPException) as error:
        PayPalSandboxClient()
    assert error.value.status_code == 503

    monkeypatch.setattr(
        settings,
        "PAYPAL_API_BASE_URL",
        f"https://{PAYPAL_SANDBOX_HOST}",
    )
    real_client = httpx.AsyncClient
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200, json={"access_token": "sandbox-access", "expires_in": 3600}
            )
        return httpx.Response(200, json={"status": "CREATED"})

    monkeypatch.setattr(
        paypal_api.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            PayPalSandboxClient().capture_order("ORDER-123", "capture-request-1")
        )
    assert error.value.status_code == 409
    assert paths == ["/v1/oauth2/token", "/v2/checkout/orders/ORDER-123"]


def test_paypal_webhook_signature_is_verified_by_paypal(monkeypatch) -> None:
    from app.services import paypal_api

    monkeypatch.setattr(paypal_api, "_token_cache", {})
    monkeypatch.setattr(settings, "PAYPAL_SANDBOX_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "PAYPAL_API_BASE_URL",
        f"https://{PAYPAL_SANDBOX_HOST}",
    )
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-secret")
    monkeypatch.setattr(settings, "PAYPAL_WEBHOOK_ID", "WEBHOOK-123")
    real_client = httpx.AsyncClient
    submitted = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200, json={"access_token": "sandbox-access", "expires_in": 3600}
            )
        submitted.update(json.loads(request.read()))
        return httpx.Response(200, json={"verification_status": "SUCCESS"})

    monkeypatch.setattr(
        paypal_api.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    event = {"id": "WH-EVENT-1", "event_type": "CHECKOUT.ORDER.APPROVED"}
    headers = {
        "PayPal-Auth-Algo": "SHA256withRSA",
        "PayPal-Cert-Url": "https://api-m.sandbox.paypal.com/cert",
        "PayPal-Transmission-Id": "transmission-123",
        "PayPal-Transmission-Sig": "signature",
        "PayPal-Transmission-Time": "2026-11-03T00:00:00Z",
    }

    verified = asyncio.run(PayPalSandboxClient().verify_webhook(headers, event))
    assert verified is True
    assert submitted["webhook_id"] == "WEBHOOK-123"
    assert submitted["webhook_event"] == event


def test_sanctions_provider_refuses_non_https_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SANCTIONS_SCREENING_ENABLED", True)
    monkeypatch.setattr(settings, "SANCTIONS_API_URL", "http://screen.example/screen")
    monkeypatch.setattr(settings, "SANCTIONS_API_TOKEN", "test-token")
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            SanctionsProvider().screen(
                SanctionsScreenRequest(full_name="Example Person")
            )
        )
    assert error.value.status_code == 503


def test_sanctions_provider_requires_exact_allowlisted_host(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SANCTIONS_SCREENING_ENABLED", True)
    monkeypatch.setattr(settings, "SANCTIONS_API_URL", "https://127.0.0.1/screen")
    monkeypatch.setattr(settings, "SANCTIONS_API_TOKEN", "test-token")
    monkeypatch.setattr(settings, "SANCTIONS_ALLOWED_HOSTS", ["screen.example"])
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            SanctionsProvider().screen(
                SanctionsScreenRequest(full_name="Example Person")
            )
        )
    assert error.value.status_code == 503
