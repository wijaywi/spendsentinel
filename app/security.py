"""OIDC access-token validation and route authorization dependencies."""

from functools import lru_cache
from typing import Any, Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def principal_has_scope(principal: dict[str, Any], required_scope: str) -> bool:
    """Check normalized scope and role claims without trusting malformed types."""
    scope_claim = principal.get("scope", principal.get("scp", ""))
    if isinstance(scope_claim, str):
        scopes = set(scope_claim.split())
    elif isinstance(scope_claim, list) and all(
        isinstance(scope, str) for scope in scope_claim
    ):
        scopes = set(scope_claim)
    else:
        scopes = set()
    roles = principal.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]
    if isinstance(roles, list) and all(isinstance(role, str) for role in roles):
        scopes.update(roles)
    return required_scope in scopes or "sentinel:admin" in scopes


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not settings.OIDC_JWKS_URL:
        raise RuntimeError("OIDC_JWKS_URL is not configured")
    return PyJWKClient(settings.OIDC_JWKS_URL, timeout=5, cache_jwk_set=True)


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate signature and standard OIDC claims using the configured JWKS."""
    if not settings.OIDC_ISSUER or not settings.OIDC_AUDIENCE:
        raise RuntimeError("OIDC issuer and audience must be configured")
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=settings.OIDC_ALGORITHMS,
        issuer=settings.OIDC_ISSUER,
        audience=settings.OIDC_AUDIENCE,
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        leeway=30,
    )
    if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
        raise jwt.InvalidTokenError("Token subject is missing")
    return claims


async def authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Return a verified principal, or a local-only development principal."""
    if not settings.AUTH_ENABLED and settings.APP_ENV.lower() != "production":
        return {
            "sub": "local-demo",
            "scope": "sentinel:read sentinel:admin",
            "development_mode": True,
        }
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except (jwt.PyJWTError, RuntimeError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token could not be verified",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_scopes(*required_scopes: str) -> Callable[..., Any]:
    """Create a dependency requiring all listed scopes or roles."""
    async def dependency(
        principal: dict[str, Any] = Depends(authenticated_user),
    ) -> dict[str, Any]:
        if not all(principal_has_scope(principal, scope) for scope in required_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return principal

    return dependency
