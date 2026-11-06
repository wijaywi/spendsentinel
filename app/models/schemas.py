"""Pydantic schemas for SpendSentinel modules."""

from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Module 1: Pre-Transaction Validation Schemas
# ---------------------------------------------------------------------------


class CheckResult(BaseModel):
    """Result of an individual pre-transaction verification check."""

    model_config = ConfigDict(from_attributes=True)

    check_name: str = Field(..., description="Name of the check executed")
    status: str = Field(..., description="Status: PASS, WARN, or FAIL")
    message: str = Field(..., description="Summary message of the check result")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Detailed diagnostic data"
    )


class PaymentValidationRequest(BaseModel):
    """Payload for validating a payment before submission."""

    model_config = ConfigDict(from_attributes=True)

    recipient_name: str = Field(..., description="Name of the recipient")
    recipient_account: str = Field(
        ..., description="Recipient IBAN or account number"
    )
    bank_code: str = Field(..., description="Recipient bank SWIFT/BIC code")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="ISO 4217 currency code"
    )
    amount: Decimal = Field(..., gt=0, description="Payment transfer amount")
    sender_country: str = Field(
        ..., min_length=2, max_length=2, description="ISO sender country code"
    )
    recipient_country: str = Field(
        ..., min_length=2, max_length=2, description="ISO recipient country code"
    )
    payment_reference: Optional[str] = Field(
        default="", description="Payment reference or memo"
    )
    purpose: Optional[str] = Field(
        default="", description="Payment purpose code or description"
    )


class ValidationResult(BaseModel):
    """Overall pre-transaction validation response."""

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(..., description="Overall status: PASS, WARN, or BLOCK")
    checks: list[CheckResult] = Field(
        default_factory=list, description="List of performed checks"
    )
    risk_score: float = Field(
        ..., ge=0.0, le=100.0, description="Calculated risk score between 0 and 100"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )


# ---------------------------------------------------------------------------
# Module 2: Agent Guard Schemas
# ---------------------------------------------------------------------------


class AgentRegistration(BaseModel):
    """Registration and configuration schema for an AI autonomous agent."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: str = Field(..., description="Unique agent identifier")
    agent_name: str = Field(..., description="Human-readable agent name")
    owner_id: str = Field(..., description="Owner or merchant identifier")
    description: Optional[str] = Field(
        default=None, description="Agent operational description"
    )
    allowed_merchants: list[str] = Field(
        default_factory=list, description="Whitelisted merchant IDs"
    )
    allowed_categories: list[str] = Field(
        default_factory=list, description="Allowed Merchant Category Codes (MCC)"
    )
    max_transaction_amount: Decimal = Field(
        ..., gt=0, description="Maximum amount allowed per transaction"
    )
    daily_spending_limit: Decimal = Field(
        ..., gt=0, description="Maximum total spend per calendar day"
    )
    currency: str = Field(
        default="USD", min_length=3, max_length=3, description="Base currency"
    )
    requires_human_approval_above: Decimal = Field(
        ..., gt=0, description="Transaction threshold requiring human approval"
    )
    allowed_currencies: list[str] = Field(
        default_factory=lambda: ["USD"], description="List of allowed currencies"
    )


class AgentTransactionRequest(BaseModel):
    """Transaction request initiated by an autonomous agent."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: str = Field(..., description="Identifier of the executing agent")
    merchant_id: str = Field(..., description="Target merchant identifier")
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(
        default="USD", min_length=3, max_length=3, description="ISO currency code"
    )
    item_description: str = Field(
        ..., description="Description of the item or service being purchased"
    )
    category_code: str = Field(
        ..., description="Merchant category code (MCC) for the item"
    )
    idempotency_key: str = Field(
        ..., description="Unique idempotency key to prevent double spending"
    )


class AgentDecision(BaseModel):
    """Decision evaluated by Agent Guard policies."""

    model_config = ConfigDict(from_attributes=True)

    decision: str = Field(
        ..., description="Decision outcome: APPROVE, DENY, or ESCALATE"
    )
    reason: str = Field(..., description="Explanation for the decision")
    policy_violations: list[str] = Field(
        default_factory=list, description="List of policy violations if any"
    )
    remaining_daily_budget: Decimal = Field(
        ..., description="Remaining daily spending budget"
    )
    audit_id: str = Field(..., description="Unique audit record identifier")


# ---------------------------------------------------------------------------
# Module 3: Evidence Vault Schemas
# ---------------------------------------------------------------------------


class DeviceFingerprint(BaseModel):
    """Device and browser fingerprint metadata."""

    model_config = ConfigDict(from_attributes=True)

    ip: str = Field(..., description="Client IP address")
    user_agent: str = Field(..., description="Client user agent string")
    device_id: str = Field(..., description="Unique hardware or browser device identifier")
    browser_language: str = Field(
        ..., description="Browser language setting, e.g. en-US"
    )


class ShippingInfo(BaseModel):
    """Fulfillment and shipping verification metadata."""

    model_config = ConfigDict(from_attributes=True)

    carrier: str = Field(..., description="Shipping carrier name")
    tracking_number: str = Field(..., description="Carrier tracking number")
    estimated_delivery: Optional[str] = Field(
        default=None, description="Estimated delivery date"
    )
    delivery_confirmed: bool = Field(
        default=False, description="Whether delivery has been verified"
    )


class CustomerHistory(BaseModel):
    """Historical behavior metrics for the customer."""

    model_config = ConfigDict(from_attributes=True)

    previous_successful_transactions: int = Field(
        default=0, ge=0, description="Count of prior successful orders"
    )
    account_age_days: int = Field(
        default=0, ge=0, description="Customer account age in days"
    )
    dispute_count: int = Field(
        default=0, ge=0, description="Number of prior disputes filed"
    )


class PaymentDetails(BaseModel):
    """Payment transaction details."""

    model_config = ConfigDict(from_attributes=True)

    amount: Decimal = Field(..., gt=0, description="Transaction payment amount")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="ISO currency code"
    )
    payment_method: str = Field(..., description="Payment method used")
    billing_address_verified: bool = Field(
        default=False, description="Whether billing address AVS was verified"
    )


class TransactionEvidence(BaseModel):
    """Complete evidence package associated with a transaction."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: str = Field(..., description="Unique transaction identifier")
    order_id: str = Field(..., description="Associated order identifier")
    device_fingerprint: DeviceFingerprint = Field(
        ..., description="Device fingerprint details"
    )
    shipping_info: ShippingInfo = Field(
        ..., description="Shipping and tracking details"
    )
    customer_history: CustomerHistory = Field(
        ..., description="Customer historical profile"
    )
    payment_details: PaymentDetails = Field(
        ..., description="Payment verification details"
    )


class DisputeAutoResponse(BaseModel):
    """Automated dispute defense package and assessment."""

    model_config = ConfigDict(from_attributes=True)

    dispute_id: str = Field(..., description="Unique dispute identifier")
    evidence_package: TransactionEvidence = Field(
        ..., description="Compiled evidence package"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=100.0, description="Confidence score between 0 and 100"
    )
    recommended_action: str = Field(
        ..., description="Recommended action: ACCEPT, CONTEST, or ESCALATE"
    )
    matching_criteria: list[str] = Field(
        default_factory=list, description="Criteria matched supporting defense"
    )


class EvidenceSearchResult(BaseModel):
    """Search summary of evidence available for a transaction."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: str = Field(..., description="Unique transaction identifier")
    evidence_count: int = Field(
        ..., ge=0, description="Number of evidence points recorded"
    )
    has_device_match: bool = Field(
        ..., description="Indicates if device fingerprint matches prior history"
    )
    has_delivery_proof: bool = Field(
        ..., description="Indicates if verified delivery proof exists"
    )
    has_prior_history: bool = Field(
        ..., description="Indicates if customer has positive prior transaction history"
    )
    auto_contestable: bool = Field(
        ..., description="Indicates if evidence is sufficient for automatic dispute contest"
    )
