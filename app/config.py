"""Application configuration module."""

import os
from urllib.parse import urlparse
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration class for SpendSentinel."""

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sentinel.db")
    PAYPAL_SANDBOX_URL: str = os.getenv(
        "PAYPAL_SANDBOX_URL", "https://api-m.sandbox.paypal.com"
    )
    APP_NAME: str = os.getenv("APP_NAME", "SpendSentinel")
    VERSION: str = os.getenv("VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    CORS_ORIGINS: list[str] = ["http://127.0.0.1:8000", "http://localhost:8000"]
    AUTH_ENABLED: bool = False
    OIDC_ISSUER: str | None = None
    OIDC_AUDIENCE: str | None = None
    OIDC_JWKS_URL: str | None = None
    OIDC_ALGORITHMS: list[str] = ["RS256"]
    SANCTIONS_API_URL: str | None = None
    SANCTIONS_API_TOKEN: str | None = None
    SANCTIONS_ALLOWED_HOSTS: list[str] = []
    SANCTIONS_PROVIDER_NAME: str = "Unconfigured"
    SANCTIONS_SCREENING_ENABLED: bool = False
    PAYPAL_API_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    PAYPAL_CLIENT_ID: str | None = None
    PAYPAL_CLIENT_SECRET: str | None = None
    PAYPAL_WEBHOOK_ID: str | None = None
    PAYPAL_SANDBOX_ENABLED: bool = False
    AI_ENABLED: bool = False
    AI_API_URL: str = "http://127.0.0.1:1234/v1/chat/completions"
    AI_ALLOWED_HOSTS: list[str] = ["generativelanguage.googleapis.com"]
    AI_API_KEY: str | None = None
    AI_MODEL: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if any(algorithm.startswith("HS") for algorithm in self.OIDC_ALGORITHMS):
            raise ValueError("OIDC signing algorithms must be asymmetric")
        for field_name in ("OIDC_ISSUER", "OIDC_JWKS_URL"):
            value = getattr(self, field_name)
            if value and urlparse(value).scheme != "https":
                raise ValueError(f"{field_name} must use HTTPS")
        if self.APP_ENV.lower() == "production":
            missing = [
                key
                for key, value in {
                    "AUTH_ENABLED": self.AUTH_ENABLED,
                    "OIDC_ISSUER": self.OIDC_ISSUER,
                    "OIDC_AUDIENCE": self.OIDC_AUDIENCE,
                    "OIDC_JWKS_URL": self.OIDC_JWKS_URL,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(
                    "Production requires authentication and OIDC configuration: "
                    + ", ".join(missing)
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            origins = [urlparse(origin) for origin in self.CORS_ORIGINS]
            if not origins or any(
                origin.scheme != "https"
                or not origin.netloc
                or origin.path not in ("", "/")
                or origin.query
                or origin.fragment
                or "*" in origin.netloc
                or origin.username is not None
                or origin.password is not None
                for origin in origins
            ):
                raise ValueError(
                    "Production CORS_ORIGINS must contain only HTTPS origins"
                )
            if self.PAYPAL_API_BASE_URL != "https://api-m.sandbox.paypal.com":
                raise ValueError(
                    "Live PayPal execution is disabled in this release; sandbox API URL is required"
                )
        return self

    @property
    def async_database_url(self) -> str:
        """Return database URL formatted for SQLAlchemy async SQLite driver."""
        url = self.DATABASE_URL
        if url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite:///"):
            return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return url


settings = Settings()
