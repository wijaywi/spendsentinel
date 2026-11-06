"""Request and response models for compliance and payment integrations."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.data.currencies import get_currency_info, validate_currency


class SanctionsStatus(str, Enum):
    CLEAR = "CLEAR"
    POTENTIAL_MATCH = "POTENTIAL_MATCH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class SanctionsScreenRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    date_of_birth: date | None = None
    reference: str | None = Field(default=None, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("full_name must contain at least two characters")
        return normalized

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class SanctionsMatch(BaseModel):
    name: str
    list_name: str
    program: str | None = None
    score: float = Field(..., ge=0, le=100)
    source_id: str | None = None


class SanctionsScreenResponse(BaseModel):
    provider: str
    status: SanctionsStatus
    checked_at: datetime
    source_updated_at: datetime | None = None
    matches: list[SanctionsMatch] = Field(default_factory=list)
    requires_human_review: bool = True
    authoritative_decision: bool = False


class PayPalOrderRequest(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"))
    currency: str = Field(..., min_length=3, max_length=3)
    reference_id: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=127)
    request_id: str = Field(
        ...,
        min_length=8,
        max_length=108,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        valid, reason = validate_currency(normalized)
        if not valid:
            raise ValueError(reason)
        return normalized

    @field_validator("request_id", "reference_id")
    @classmethod
    def trim_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @model_validator(mode="after")
    def validate_money_precision(self) -> "PayPalOrderRequest":
        minor_units = get_currency_info(self.currency).get("minor_units", 2)
        if max(0, -self.amount.as_tuple().exponent) > minor_units:
            raise ValueError(
                f"amount may use at most {minor_units} decimal places for {self.currency}"
            )
        return self
