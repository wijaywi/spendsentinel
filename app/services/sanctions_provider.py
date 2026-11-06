"""Fail-closed adapter for an authorized sanctions-screening provider."""

from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.schemas.integrations import (
    SanctionsScreenRequest,
    SanctionsScreenResponse,
    SanctionsStatus,
)


class SanctionsProvider:
    """Calls a configured provider adapter using Sentinel's normalized JSON contract."""

    def __init__(self) -> None:
        self.endpoint = settings.SANCTIONS_API_URL
        self.token = settings.SANCTIONS_API_TOKEN
        self.provider_name = settings.SANCTIONS_PROVIDER_NAME

    async def screen(
        self, request: SanctionsScreenRequest
    ) -> SanctionsScreenResponse:
        if not settings.SANCTIONS_SCREENING_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sanctions screening integration is disabled",
            )
        if not self.endpoint or not self.token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authorized sanctions-screening provider is not configured",
            )
        try:
            parsed = urlparse(self.endpoint)
            parsed_port = parsed.port
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sanctions provider endpoint is invalid",
            ) from exc
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed_port not in (None, 443)
            or parsed.hostname.lower() not in {
                host.strip().lower() for host in settings.SANCTIONS_ALLOWED_HOSTS
            }
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sanctions endpoint must use HTTPS and an explicitly allowed host",
            )

        payload = {
            "full_name": request.full_name,
            "country": request.country,
            "date_of_birth": (
                request.date_of_birth.isoformat() if request.date_of_birth else None
            ),
            "reference": request.reference,
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(8.0), follow_redirects=False
            ) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                response.raise_for_status()
                body = response.json()
            result = SanctionsScreenResponse.model_validate(
                {**body, "provider": self.provider_name}
            )
            if (
                result.status == SanctionsStatus.CLEAR
                and result.matches
            ):
                raise ValueError("Provider returned CLEAR together with matches")
            return result
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sanctions provider could not return a valid screening result",
            ) from exc


def screening_unavailable_result() -> SanctionsScreenResponse:
    """Describe the fail-closed state without implying a person was cleared."""
    return SanctionsScreenResponse(
        provider=settings.SANCTIONS_PROVIDER_NAME,
        status=SanctionsStatus.REVIEW_REQUIRED,
        checked_at=datetime.now(timezone.utc),
        requires_human_review=True,
        authoritative_decision=False,
    )
