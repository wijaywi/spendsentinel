"""Pydantic schemas for Agent Commerce Guard."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.data.currencies import validate_currency
from app.data.currencies import get_currency_info


class AgentDecisionEnum(str, Enum):
    """Possible outcomes for an agent transaction policy evaluation."""

    APPROVE = "APPROVE"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class AgentRegistration(BaseModel):
    """Schema for registering a new AI agent with spending policies."""

    agent_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Unique identifier for the agent",
    )
    name: str = Field(..., min_length=1, max_length=128, description="Human-readable name")
    owner_id: str = Field(..., min_length=1, max_length=64, description="Owner identifier")
    description: Optional[str] = Field(None, max_length=500)
    max_transaction_amount: Decimal = Field(
        ..., gt=Decimal("0"), description="Maximum amount allowed per transaction"
    )
    daily_spending_limit: Decimal = Field(
        ..., gt=Decimal("0"), description="Maximum aggregated amount allowed per UTC day"
    )
    allowed_currencies: list[str] = Field(
        ..., min_length=1, description="List of authorized 3-letter currency codes (e.g., USD)"
    )
    budget_currency: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Currency denomination for the daily spending limit",
    )
    allowed_merchants: list[str] = Field(
        default_factory=list,
        description="Allowed merchant IDs (empty list permits all merchants)",
    )
    allowed_categories: list[str] = Field(
        default_factory=list,
        description="Allowed 4-digit MCC codes (empty list permits all categories)",
    )
    requires_human_approval_above: Optional[Decimal] = Field(
        None,
        gt=Decimal("0"),
        description="Transactions exceeding this amount require human approval",
    )

    @field_validator("allowed_currencies")
    @classmethod
    def validate_currencies(cls, currencies: list[str]) -> list[str]:
        """Validate and normalize currencies to uppercase 3-letter strings."""
        if not currencies:
            raise ValueError("allowed_currencies must contain at least one currency")
        normalized: list[str] = []
        for code in currencies:
            code_clean = code.strip().upper()
            is_valid, reason = validate_currency(code_clean)
            if not is_valid:
                raise ValueError(f"Invalid currency code '{code}': {reason}")
            normalized.append(code_clean)
        return normalized

    @field_validator("budget_currency", mode="before")
    @classmethod
    def normalize_budget_currency(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper()
        is_valid, reason = validate_currency(normalized)
        if not is_valid:
            raise ValueError(f"Invalid budget_currency '{normalized}': {reason}")
        return normalized

    @field_validator("allowed_categories")
    @classmethod
    def validate_categories(cls, categories: list[str]) -> list[str]:
        """Validate that all category items are 4-digit MCC strings."""
        normalized: list[str] = []
        for cat in categories:
            cat_clean = cat.strip()
            if not (cat_clean.isdigit() and len(cat_clean) == 4):
                raise ValueError(f"Invalid MCC code '{cat}'. Must be a 4-digit numeric string.")
            normalized.append(cat_clean)
        return normalized

    @model_validator(mode="after")
    def validate_spending_limits(self) -> "AgentRegistration":
        """Verify that daily spending limit is at least equal to single transaction limit."""
        if self.budget_currency is None:
            self.budget_currency = self.allowed_currencies[0]
        if self.daily_spending_limit < self.max_transaction_amount:
            raise ValueError(
                "daily_spending_limit cannot be less than max_transaction_amount"
            )
        if (
            self.requires_human_approval_above is not None
            and self.requires_human_approval_above > self.max_transaction_amount
        ):
            raise ValueError(
                "requires_human_approval_above cannot exceed max_transaction_amount"
            )
        if self.budget_currency not in self.allowed_currencies:
            raise ValueError("budget_currency must be included in allowed_currencies")
        minor_units = get_currency_info(self.budget_currency).get("minor_units", 2)
        amounts = [
            self.max_transaction_amount,
            self.daily_spending_limit,
            self.requires_human_approval_above,
        ]
        if any(
            amount is not None
            and max(0, -amount.as_tuple().exponent) > minor_units
            for amount in amounts
        ):
            raise ValueError(
                f"Spending policy amounts may use at most {minor_units} decimal places "
                f"for {self.budget_currency}"
            )
        return self


class AgentPolicyUpdate(BaseModel):
    """Schema for updating an existing agent's policy limits."""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, pattern=r"^(ACTIVE|INACTIVE)$")
    max_transaction_amount: Optional[Decimal] = Field(None, gt=Decimal("0"))
    daily_spending_limit: Optional[Decimal] = Field(None, gt=Decimal("0"))
    allowed_currencies: Optional[list[str]] = Field(None, min_length=1)
    budget_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    allowed_merchants: Optional[list[str]] = None
    allowed_categories: Optional[list[str]] = None
    requires_human_approval_above: Optional[Decimal] = Field(None, gt=Decimal("0"))

    @field_validator("allowed_currencies")
    @classmethod
    def validate_currencies(cls, currencies: Optional[list[str]]) -> Optional[list[str]]:
        """Validate currencies if provided in update payload."""
        if currencies is None:
            return None
        if not currencies:
            raise ValueError("allowed_currencies must contain at least one currency")
        normalized: list[str] = []
        for code in currencies:
            code_clean = code.strip().upper()
            is_valid, reason = validate_currency(code_clean)
            if not is_valid:
                raise ValueError(f"Invalid currency code '{code}': {reason}")
            normalized.append(code_clean)
        return normalized

    @field_validator("budget_currency", mode="before")
    @classmethod
    def normalize_budget_currency(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper()
        is_valid, reason = validate_currency(normalized)
        if not is_valid:
            raise ValueError(f"Invalid budget_currency '{normalized}': {reason}")
        return normalized

    @field_validator("allowed_categories")
    @classmethod
    def validate_categories(cls, categories: Optional[list[str]]) -> Optional[list[str]]:
        """Validate categories if provided in update payload."""
        if categories is None:
            return None
        normalized: list[str] = []
        for cat in categories:
            cat_clean = cat.strip()
            if not (cat_clean.isdigit() and len(cat_clean) == 4):
                raise ValueError(f"Invalid MCC code '{cat}'. Must be a 4-digit numeric string.")
            normalized.append(cat_clean)
        return normalized


class AgentProfile(BaseModel):
    """Schema representing an active agent profile."""

    agent_id: str
    name: str
    owner_id: str
    description: Optional[str] = None
    status: str
    max_transaction_amount: Decimal
    daily_spending_limit: Decimal
    budget_currency: str = "USD"
    allowed_currencies: list[str]
    allowed_merchants: list[str]
    allowed_categories: list[str]
    requires_human_approval_above: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentTransactionRequest(BaseModel):
    """Schema for evaluating an agent transaction against merchant policies."""

    idempotency_key: str = Field(..., min_length=1, max_length=128)
    agent_id: str = Field(..., min_length=1, max_length=64)
    amount: Decimal = Field(..., gt=Decimal("0"), description="Transaction amount")
    currency: str = Field(..., min_length=3, max_length=3)
    merchant_id: str = Field(..., min_length=1, max_length=64)
    merchant_name: Optional[str] = Field(None, max_length=128)
    category_mcc: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=256)
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("idempotency_key", "agent_id", "merchant_id", mode="before")
    @classmethod
    def trim_identifiers(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("identifier must not be blank")
        return normalized

    @field_validator("category_mcc")
    @classmethod
    def validate_mcc(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            cleaned = value.strip()
            if not (cleaned.isdigit() and len(cleaned) == 4):
                raise ValueError("category_mcc must be a four-digit numeric code")
            return cleaned
        return value

    @model_validator(mode="after")
    def validate_amount_precision(self) -> "AgentTransactionRequest":
        is_valid, reason = validate_currency(self.currency)
        if not is_valid:
            raise ValueError(reason)
        minor_units = get_currency_info(self.currency).get("minor_units", 2)
        if max(0, -self.amount.as_tuple().exponent) > minor_units:
            raise ValueError(
                f"amount may use at most {minor_units} decimal places for {self.currency}"
            )
        return self


class AgentIntentRequest(BaseModel):
    """Natural-language purchase intent submitted for AI extraction and policy review."""

    idempotency_key: str = Field(..., min_length=1, max_length=128)
    agent_id: str = Field(..., min_length=1, max_length=64)
    merchant_id: str = Field(..., min_length=1, max_length=64)
    instruction: str = Field(..., min_length=5, max_length=1000)

    @field_validator("idempotency_key", "agent_id", "merchant_id", mode="before")
    @classmethod
    def trim_identifiers(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("identifier must not be blank")
        return normalized

    @field_validator("instruction")
    @classmethod
    def trim_instruction(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 5:
            raise ValueError("instruction must contain at least five characters")
        return normalized


class AgentIntentExtraction(BaseModel):
    """AI-extracted purchase fields, subject to normal transaction validation."""

    amount: str = Field(..., min_length=1, max_length=32)
    currency: str = Field(..., min_length=3, max_length=3)
    merchant_name: str | None = Field(default=None, max_length=128)
    category_mcc: str | None = Field(default=None, max_length=4)
    description: str = Field(..., min_length=1, max_length=256)

    model_config = ConfigDict(extra="forbid")

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("amount", "description")
    @classmethod
    def trim_required_values(cls, value: str) -> str:
        return value.strip()

    @field_validator("merchant_name", "category_mcc")
    @classmethod
    def trim_optional_values(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class AgentDecision(BaseModel):
    """Schema representing the evaluation decision for an agent transaction."""

    decision: AgentDecisionEnum
    agent_id: str
    transaction_id: Optional[str] = None
    idempotency_key: str
    amount: Decimal
    currency: str
    violations: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    risk_score: float
    requires_human_approval: bool = False
    cached: bool = False
    evaluated_at: datetime


class AgentIntentEvaluationResponse(BaseModel):
    """AI extraction and deterministic Agent Guard decision."""

    ai_model: str
    extracted_intent: AgentIntentExtraction
    decision: AgentDecision


class AgentSpendingSummary(BaseModel):
    """Schema for daily spending aggregate report."""

    agent_id: str
    date: str
    total_spent: Decimal
    transaction_count: int
    daily_spending_limit: Decimal
    budget_currency: str = "USD"
    remaining_budget: Decimal


class AuditLogResponse(BaseModel):
    """Schema for returning audit trail entries."""

    id: str
    agent_id: str
    event_type: str
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentDetailResponse(BaseModel):
    """Schema combining agent profile and active spending summary."""

    agent: AgentProfile
    spending: AgentSpendingSummary
