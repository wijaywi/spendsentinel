"""Production-oriented compliance and sandbox payment integration routes."""

import re

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.models.payment_event import PayPalWebhookEvent
from app.schemas.integrations import (
    PayPalOrderRequest,
    SanctionsScreenRequest,
    SanctionsScreenResponse,
)
from app.security import require_scopes
from app.services.paypal_api import PayPalSandboxClient
from app.services.sanctions_provider import SanctionsProvider

router = APIRouter(prefix="/api", tags=["Compliance and Payments"])
webhook_router = APIRouter(prefix="/api/payments", tags=["PayPal Webhooks"])


@router.get("/integrations/status")
async def integration_status(
    _principal: dict = Depends(require_scopes("sentinel:read")),
) -> dict[str, object]:
    """Expose configuration state without returning secrets or endpoints."""
    return {
        "authentication": {
            "enabled": settings.AUTH_ENABLED,
            "issuer_configured": bool(settings.OIDC_ISSUER),
        },
        "sanctions_screening": {
            "configured": bool(
                settings.SANCTIONS_SCREENING_ENABLED
                and settings.SANCTIONS_API_URL
                and settings.SANCTIONS_API_TOKEN
            ),
            "provider": settings.SANCTIONS_PROVIDER_NAME
            if settings.SANCTIONS_SCREENING_ENABLED
            and settings.SANCTIONS_API_URL
            and settings.SANCTIONS_API_TOKEN
            else None,
        },
        "paypal": {
            "configured": bool(
                settings.PAYPAL_SANDBOX_ENABLED
                and settings.PAYPAL_CLIENT_ID
                and settings.PAYPAL_CLIENT_SECRET
            ),
            "environment": "sandbox",
            "webhook_configured": bool(settings.PAYPAL_WEBHOOK_ID),
        },
    }


@router.post(
    "/compliance/screen",
    response_model=SanctionsScreenResponse,
    summary="Screen a party with the configured compliance provider",
)
async def screen_party(
    request: SanctionsScreenRequest,
    _principal: dict = Depends(require_scopes("sentinel:compliance:screen")),
) -> SanctionsScreenResponse:
    """Call the licensed screening adapter; unavailable provider fails closed."""
    return await SanctionsProvider().screen(request)


@router.post(
    "/payments/orders",
    status_code=status.HTTP_201_CREATED,
    summary="Create a PayPal sandbox checkout order",
)
async def create_paypal_order(
    request: PayPalOrderRequest,
    _principal: dict = Depends(require_scopes("sentinel:payments:create")),
) -> dict:
    """Create an order in PayPal sandbox. This does not capture or transfer funds."""
    return await PayPalSandboxClient().create_order(request)


@router.post(
    "/payments/orders/{order_id}/capture",
    summary="Capture a buyer-approved PayPal sandbox order",
)
async def capture_paypal_order(
    order_id: str,
    request_id: str = Header(..., alias="PayPal-Request-Id", min_length=8, max_length=108),
    _principal: dict = Depends(require_scopes("sentinel:payments:capture")),
) -> dict:
    """Capture only an APPROVED order, using a caller-supplied idempotency key."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", order_id):
        raise HTTPException(status_code=400, detail="Invalid PayPal order ID")
    return await PayPalSandboxClient().capture_order(order_id, request_id)


@webhook_router.post("/webhooks/paypal", summary="Verify and deduplicate a PayPal webhook")
async def receive_paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Verify event signatures via PayPal before recording a minimal dedupe entry."""
    try:
        event = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from exc
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook event")
    event_id = event.get("id")
    event_type = event.get("event_type")
    if (
        not isinstance(event_id, str)
        or not event_id
        or len(event_id) > 128
        or not isinstance(event_type, str)
        or not event_type
        or len(event_type) > 128
    ):
        raise HTTPException(status_code=400, detail="Webhook event ID and type are required")

    verified = await PayPalSandboxClient().verify_webhook(
        dict(request.headers), event
    )
    if not verified:
        raise HTTPException(status_code=400, detail="PayPal webhook signature is invalid")

    db.add(PayPalWebhookEvent(event_id=event_id, event_type=event_type))
    try:
        db.commit()
        return {"received": True, "duplicate": False, "event_id": event_id}
    except IntegrityError:
        db.rollback()
        existing = db.get(PayPalWebhookEvent, event_id)
        if existing is None:
            raise
        return {"received": True, "duplicate": True, "event_id": event_id}
