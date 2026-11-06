"""FastAPI router for Evidence Vault and Dispute Prevention Shield."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.evidence_vault import EvidenceVault
from app.schemas.evidence import (
    TransactionEvidence,
    EvidenceRecord,
    EvidenceSearchResult,
    DisputeResponseRequest,
    DisputeAutoResponse,
    CustomerProfileResponse,
    EvidenceStatsResponse,
)
from app.security import require_scopes

router = APIRouter(prefix="/api/evidence", tags=["Evidence Vault"])


@router.post("/store", response_model=EvidenceRecord, status_code=status.HTTP_201_CREATED)
def store_evidence(
    evidence: TransactionEvidence,
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:evidence:write")),
) -> EvidenceRecord:
    """Store transaction evidence proactively into the immutable Evidence Vault.

    Computes completeness strength score (0-100) based on fulfillment, device identity,
    prior purchase history, and address verification. If updated evidence is submitted
    for an existing transaction, a new version is appended to preserve the audit trail.
    """
    try:
        service = EvidenceVault(db)
        return service.store_evidence(evidence)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store evidence: {str(exc)}",
        )


@router.get("/{transaction_id}", response_model=EvidenceSearchResult)
def search_evidence(
    transaction_id: str,
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:read")),
) -> EvidenceSearchResult:
    """Search the Evidence Vault for all records linked to a transaction.

    Returns the latest evidence record, complete immutable version history, and
    a dispute contestability assessment.
    """
    if not transaction_id or not transaction_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction ID cannot be empty.",
        )

    service = EvidenceVault(db)
    result = service.search_evidence(transaction_id)
    if not result.evidence_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evidence records found for transaction ID '{transaction_id}'.",
        )
    return result


@router.post("/dispute-response", response_model=DisputeAutoResponse)
def prepare_dispute_response(
    request: DisputeResponseRequest,
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:disputes:prepare")),
) -> DisputeAutoResponse:
    """Prepare an automated dispute response package inspired by Visa Compelling Evidence 3.0 principles.

    Correlates disputed transaction against historical buyer activity within the 120-365
    day window, evaluates matching device and IP fingerprints, and generates a structured
    rebuttal package with a recommended action (CONTEST, ESCALATE, ACCEPT).
    """
    if not request.dispute_id or not request.dispute_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dispute ID is required.",
        )
    if not request.transaction_id or not request.transaction_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction ID is required.",
        )

    service = EvidenceVault(db)
    return service.prepare_dispute_response(request.dispute_id, request.transaction_id)


@router.get("/customer-profile/{device_id}", response_model=CustomerProfileResponse)
def get_customer_profile(
    device_id: str,
    ip_address: Optional[str] = Query(None, description="Optional IP address for network telemetry correlation"),
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:read")),
) -> CustomerProfileResponse:
    """Retrieve customer behavioral profile by device fingerprint identifier.

    Aggregates transaction history, dispute rate, average order value, and risk classification
    across all orders associated with the device or IP address.
    """
    if not device_id or not device_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device ID parameter cannot be empty.",
        )

    service = EvidenceVault(db)
    fingerprint = {"device_id": device_id}
    if ip_address:
        fingerprint["ip_address"] = ip_address

    profile_data = service.get_customer_profile(fingerprint)
    return CustomerProfileResponse(**profile_data)


@router.post("/bulk-store", response_model=List[EvidenceRecord], status_code=status.HTTP_201_CREATED)
def bulk_store_evidence(
    evidences: List[TransactionEvidence],
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:evidence:write")),
) -> List[EvidenceRecord]:
    """Store transaction evidence in bulk for batch processing and order ingestion.

    Maintains individual scoring and immutable append-only versioning for each transaction.
    """
    if not evidences:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evidence list cannot be empty.",
        )

    service = EvidenceVault(db)
    return service.bulk_store_evidence(evidences)


@router.get("/stats", response_model=EvidenceStatsResponse)
def get_evidence_stats(
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:read")),
) -> EvidenceStatsResponse:
    """Retrieve overall Evidence Vault statistics.

    Includes total records, average evidence completeness strength, and auto-contestable count.
    """
    service = EvidenceVault(db)
    stats = service.get_evidence_stats()
    return EvidenceStatsResponse(**stats)
