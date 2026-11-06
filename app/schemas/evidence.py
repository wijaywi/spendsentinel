"""Pydantic schemas for Evidence Vault requests and responses."""

from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


class TransactionEvidence(BaseModel):
    """Input payload representing proactively captured transaction evidence."""

    transaction_id: str = Field(..., description="Unique transaction identifier")
    customer_id: str = Field(..., description="Customer or account identifier")
    amount: float = Field(..., ge=0.0, description="Transaction monetary amount")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    timestamp: Optional[datetime] = Field(default=None, description="Original transaction timestamp")

    # Device fingerprint (device_id, ip_address, user_agent, screen_resolution, etc.)
    device_fingerprint: Optional[Dict[str, Any]] = Field(default=None, description="Device and network fingerprint")

    # Address details
    shipping_address: Optional[Dict[str, Any]] = Field(default=None, description="Physical shipping address details")
    billing_address: Optional[Dict[str, Any]] = Field(default=None, description="Billing address details")
    billing_address_verified: bool = Field(default=False, description="Whether billing address was verified via AVS")

    # Fulfillment / Delivery details
    delivery_tracking_number: Optional[str] = Field(default=None, description="Carrier tracking code")
    delivery_carrier: Optional[str] = Field(default=None, description="Carrier name (e.g. FedEx, UPS, DHL)")
    delivery_status: Optional[str] = Field(default=None, description="Tracking status (DELIVERED, IN_TRANSIT, etc.)")
    delivery_confirmed: bool = Field(default=False, description="Whether delivery confirmation with signature exists")

    # Product / service description
    item_description: Optional[str] = Field(default=None, description="Description of purchased items or services")

    # Append-only linkage
    parent_record_id: Optional[str] = Field(default=None, description="Parent evidence ID for immutable updates")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional custom metadata dictionary")


class EvidenceStrengthBreakdown(BaseModel):
    """Granular points contributing to the evidence strength score."""

    device_fingerprint_points: int = 0
    delivery_tracking_points: int = 0
    delivery_confirmed_points: int = 0
    prior_successful_transactions_points: int = 0
    billing_address_verified_points: int = 0
    total_score: int = 0


class EvidenceRecord(BaseModel):
    """Immutable evidence record stored in the Evidence Vault."""

    id: str = Field(..., description="Unique immutable evidence record ID")
    transaction_id: str = Field(..., description="Transaction ID")
    customer_id: str = Field(..., description="Customer ID")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Currency code")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    created_at: datetime = Field(..., description="Immutable vault storage timestamp")

    device_fingerprint: Optional[Dict[str, Any]] = None
    shipping_address: Optional[Dict[str, Any]] = None
    billing_address: Optional[Dict[str, Any]] = None
    billing_address_verified: bool = False

    delivery_tracking_number: Optional[str] = None
    delivery_carrier: Optional[str] = None
    delivery_status: Optional[str] = None
    delivery_confirmed: bool = False

    item_description: Optional[str] = None
    evidence_strength: int = Field(..., ge=0, le=100, description="Evidence completeness score (0-100)")
    strength_breakdown: Optional[Dict[str, Any]] = None
    prior_successful_transactions_count: int = 0

    parent_record_id: Optional[str] = None
    version: int = 1
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class EvidenceSearchResult(BaseModel):
    """Result of searching the Evidence Vault for a transaction."""

    transaction_id: str
    evidence_found: bool
    latest_record: Optional[EvidenceRecord] = None
    history_records: List[EvidenceRecord] = []
    evidence_strength: int = 0
    contestability_status: str  # HIGHLY_CONTESTABLE, MODERATELY_CONTESTABLE, LOW_CONTESTABILITY, INSUFFICIENT_EVIDENCE
    contestability_summary: str
    qualifying_ce3_factors: List[str] = []


class DisputeResponseRequest(BaseModel):
    """Request payload to trigger auto-response preparation for a dispute."""

    dispute_id: str = Field(..., description="PayPal Dispute ID")
    transaction_id: str = Field(..., description="Transaction ID associated with dispute")


class DisputeAutoResponse(BaseModel):
    """Automated dispute defense package with recommended merchant action."""

    dispute_id: str
    transaction_id: str
    confidence_score: int = Field(..., ge=0, le=100, description="Dispute defense confidence score (0-100)")
    recommended_action: str  # CONTEST, ESCALATE, ACCEPT
    action_reason: str
    evidence_package: Dict[str, Any]
    ce3_compliance: Dict[str, Any]
    generated_at: datetime


class CustomerProfileResponse(BaseModel):
    """Customer profile aggregated across matching device or network identities."""

    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    transaction_count: int = 0
    dispute_count: int = 0
    dispute_rate: float = 0.0
    average_order_value: float = 0.0
    total_spent: float = 0.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    associated_customers: List[str] = []
    associated_customers_truncated: bool = False
    risk_assessment: str = "LOW"  # LOW, MEDIUM, HIGH


class EvidenceStatsResponse(BaseModel):
    """Statistical summary of the Evidence Vault."""

    total_records: int
    avg_evidence_strength: float
    auto_contestable_count: int
    action_breakdown: Optional[Dict[str, int]] = None
    total_dispute_responses: int = 0
