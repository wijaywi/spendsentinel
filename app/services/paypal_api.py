"""PayPal REST Orders API client restricted to PayPal's sandbox host."""

import asyncio
import hashlib
import time
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.schemas.integrations import PayPalOrderRequest

PAYPAL_SANDBOX_HOST = "api-m.sandbox.paypal.com"
_token_cache: dict[str, tuple[str, float]] = {}
_token_lock = asyncio.Lock()


class PayPalSandboxClient:
    """Create and capture PayPal Orders only against the sandbox environment."""

    def __init__(self) -> None:
        if not settings.PAYPAL_SANDBOX_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PayPal sandbox integration is disabled",
            )
        self.base_url = settings.PAYPAL_API_BASE_URL.rstrip("/")
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        parsed = urlparse(self.base_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != PAYPAL_SANDBOX_HOST
            or parsed.path not in ("", "/")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="This release permits PayPal sandbox endpoints only",
            )
        if not self.client_id or not self.client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PayPal sandbox credentials are not configured",
            )

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        cache_key = hashlib.sha256(
            f"{self.base_url}\0{self.client_id}\0{self.client_secret}".encode()
        ).hexdigest()
        async with _token_lock:
            cached = _token_cache.get(cache_key)
            if cached and cached[1] > time.monotonic():
                return cached[0]
            response = await client.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            body = response.json()
            token = body.get("access_token") if isinstance(body, dict) else None
            expires_in = body.get("expires_in", 300) if isinstance(body, dict) else None
            if not isinstance(token, str) or not token:
                raise ValueError("PayPal OAuth response omitted access_token")
            try:
                lifetime = float(expires_in)
            except (TypeError, ValueError) as exc:
                raise ValueError("PayPal OAuth response has an invalid expiry") from exc
            if lifetime <= 0:
                raise ValueError("PayPal OAuth response has an invalid expiry")
            _token_cache[cache_key] = (
                token,
                time.monotonic() + max(0.0, lifetime - 30.0),
            )
            return token

    async def create_order(self, request: PayPalOrderRequest) -> dict:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0)) as client:
                token = await self._access_token(client)
                payload = {
                    "intent": "CAPTURE",
                    "purchase_units": [
                        {
                            "reference_id": request.reference_id,
                            "description": request.description,
                            "amount": {
                                "currency_code": request.currency,
                                "value": format(request.amount, "f"),
                            },
                        }
                    ],
                    "application_context": {
                        "shipping_preference": "NO_SHIPPING",
                        "user_action": "PAY_NOW",
                    },
                }
                response = await client.post(
                    f"{self.base_url}/v2/checkout/orders",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "PayPal-Request-Id": request.request_id,
                        "Prefer": "return=representation",
                    },
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal sandbox rejected the order request",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal sandbox could not complete the order request",
            ) from exc

    async def capture_order(self, order_id: str, request_id: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0)) as client:
                token = await self._access_token(client)
                headers = {
                    "Authorization": f"Bearer {token}",
                    "PayPal-Request-Id": request_id,
                    "Prefer": "return=representation",
                }
                order_response = await client.get(
                    f"{self.base_url}/v2/checkout/orders/{order_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                order_response.raise_for_status()
                order = order_response.json()
                if order.get("status") != "APPROVED":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="PayPal order must be buyer-approved before capture",
                    )
                capture_response = await client.post(
                    f"{self.base_url}/v2/checkout/orders/{order_id}/capture",
                    headers=headers,
                )
                capture_response.raise_for_status()
                return capture_response.json()
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal sandbox rejected the capture request",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal sandbox could not complete the capture request",
            ) from exc

    async def verify_webhook(
        self, headers: dict[str, str], event: dict
    ) -> bool:
        if not settings.PAYPAL_WEBHOOK_ID:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PayPal webhook ID is not configured",
            )
        normalized_headers = {
            str(name).casefold(): value for name, value in headers.items()
        }
        required_headers = {
            "auth_algo": normalized_headers.get("paypal-auth-algo"),
            "cert_url": normalized_headers.get("paypal-cert-url"),
            "transmission_id": normalized_headers.get("paypal-transmission-id"),
            "transmission_sig": normalized_headers.get("paypal-transmission-sig"),
            "transmission_time": normalized_headers.get("paypal-transmission-time"),
        }
        if any(not value for value in required_headers.values()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Required PayPal transmission headers are missing",
            )
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0)) as client:
                token = await self._access_token(client)
                response = await client.post(
                    f"{self.base_url}/v1/notifications/verify-webhook-signature",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        **required_headers,
                        "webhook_id": settings.PAYPAL_WEBHOOK_ID,
                        "webhook_event": event,
                    },
                )
                response.raise_for_status()
                return response.json().get("verification_status") == "SUCCESS"
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal sandbox could not verify the webhook",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPal sandbox could not verify the webhook",
            ) from exc
