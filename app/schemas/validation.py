"""
Pydantic data schemas for payment validation requests, results, and batch processing.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class PaymentValidationRequest(BaseModel):
    """
    Input payload for international payment pre-transaction validation.
    """
    sender_country: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code of sender",
        examples=["US"],
    )
    recipient_country: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code of recipient",
        examples=["DE"],
    )
    recipient_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Beneficiary individual or company legal name",
        examples=["Acme GmbH"],
    )
    iban: Optional[str] = Field(
        None,
        max_length=40,
        description="International Bank Account Number if recipient is in an IBAN jurisdiction",
        examples=["DE89370400440532013000"],
    )
    bic: Optional[str] = Field(
        None,
        max_length=15,
        description="SWIFT/BIC 8 or 11 character identifier code",
        examples=["DEUTDEFF"],
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO 4217 three-letter currency code",
        examples=["EUR"],
    )
    amount: float = Field(
        ...,
        gt=0,
        allow_inf_nan=False,
        description="Payment transaction amount. Must be finite and positive.",
        examples=[1250.50],
    )
    reference: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Payment narrative, invoice reference, or remittance information",
        examples=["INV-2026-9041 Consulting Services"],
    )
    recipient_account: Optional[str] = Field(
        None,
        max_length=64,
        description="Local non-IBAN account number (e.g. US routing/account, UK sort/account)",
    )

    @field_validator("sender_country", "recipient_country", "currency", mode="before")
    @classmethod
    def normalize_upper(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("iban", "bic", mode="before")
    @classmethod
    def clean_spaces(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = "".join(value.split()).upper()
            return cleaned if cleaned else None
        return value


class CheckItem(BaseModel):
    """
    Individual validation check assessment result.
    """
    check_id: str = Field(..., description="Unique identifier of the rule check")
    name: str = Field(..., description="Human readable rule name")
    passed: bool = Field(..., description="True if check passed without blocking error")
    severity: str = Field(
        ...,
        description="Severity level: INFO, WARNING, or ERROR",
        examples=["INFO", "WARNING", "ERROR"],
    )
    score_impact: int = Field(..., description="Risk score penalty added to composite score (0-100)")
    message: str = Field(..., description="Detailed explanation of check finding")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Structured diagnostics")


class ValidationResult(BaseModel):
    """
    Composite evaluation response returned by pre-transaction validation engine.
    """
    validation_id: str = Field(..., description="Unique validation transaction ID")
    timestamp: str = Field(..., description="UTC ISO timestamp of evaluation")
    status: str = Field(
        ...,
        description="Overall decision status: PASS (score <30), WARN (30-70), BLOCK (>70)",
        examples=["PASS", "WARN", "BLOCK"],
    )
    risk_score: int = Field(..., ge=0, le=100, description="Composite risk index from 0 to 100")
    is_blocked: bool = Field(..., description="True if status is BLOCK")
    sender_country: str
    recipient_country: str
    currency: str
    amount: float
    reference: str
    checks: List[CheckItem] = Field(default_factory=list, description="Ordered validation check results")
    recommendations: List[str] = Field(default_factory=list, description="Actionable remediation steps")
    summary: str = Field(..., description="Concise summary narrative of evaluation outcome")
    execution_time_ms: float = Field(..., description="Processing time in milliseconds")


class BatchValidationRequest(BaseModel):
    """
    Batch payload containing multiple payment requests.
    """
    payments: List[PaymentValidationRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of payment validation items to evaluate (max 100)",
    )


class BatchValidationResponse(BaseModel):
    """
    Batch processing summary and list of individual validation results.
    """
    total: int = Field(..., description="Total payments evaluated")
    passed_count: int = Field(..., description="Count of passed payments")
    warned_count: int = Field(..., description="Count of payments with warnings")
    blocked_count: int = Field(..., description="Count of blocked payments")
    results: List[ValidationResult] = Field(default_factory=list)


class ValidationHistoryItem(BaseModel):
    """
    Summary view of a logged validation record.
    """
    id: str
    created_at: str
    sender_country: str
    recipient_country: str
    recipient_name: str
    currency: str
    amount: float
    reference: str
    status: str
    risk_score: int
    passed: bool
    execution_time_ms: float


class ValidationHistoryResponse(BaseModel):
    """
    Paginated list of historical validation records.
    """
    total: int
    limit: int
    offset: int
    items: List[ValidationHistoryItem]
