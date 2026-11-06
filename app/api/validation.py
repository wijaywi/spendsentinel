"""API routes for international payment pre-validation."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.validation_log import ValidationLog
from app.schemas.validation import (
    BatchValidationRequest,
    BatchValidationResponse,
    PaymentValidationRequest,
    ValidationHistoryItem,
    ValidationHistoryResponse,
    ValidationResult,
)
from app.services.pre_transaction import PreTransactionValidator
from app.security import require_scopes

router = APIRouter(prefix="/api/validation", tags=["International Payment Validation"])
validator = PreTransactionValidator()


def _validate_and_log(
    payment: PaymentValidationRequest, db: Session, *, commit: bool = True
) -> ValidationResult:
    result = validator.validate(payment, db=db)
    persisted_checks = []
    for check in result.checks:
        serialized = check.model_dump(mode="json")
        if check.check_id == "iban_validation":
            serialized["details"].pop("iban", None)
        persisted_checks.append(serialized)
    db.add(
        ValidationLog(
            id=result.validation_id,
            sender_country=payment.sender_country,
            recipient_country=payment.recipient_country,
            recipient_name=payment.recipient_name,
            recipient_account=None,
            iban=None,
            bic=payment.bic,
            currency=payment.currency,
            amount=float(payment.amount),
            reference=payment.reference,
            status=result.status,
            risk_score=result.risk_score,
            passed=not result.is_blocked,
            checks_results=persisted_checks,
            recommendations=result.recommendations,
            execution_time_ms=result.execution_time_ms,
        )
    )
    db.flush()
    if commit:
        db.commit()
    return result


@router.post("/validate", response_model=ValidationResult)
def validate_payment(
    payment: PaymentValidationRequest,
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:payments:validate")),
) -> ValidationResult:
    """Run deterministic format and corridor checks; this does not verify account ownership."""
    return _validate_and_log(payment, db)


@router.post("/validate/batch", response_model=BatchValidationResponse)
def validate_batch(
    request: BatchValidationRequest,
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:payments:validate")),
) -> BatchValidationResponse:
    """Validate up to 100 payment instructions and persist each result."""
    try:
        results = [
            _validate_and_log(payment, db, commit=False)
            for payment in request.payments
        ]
        db.commit()
    except Exception:
        db.rollback()
        raise
    return BatchValidationResponse(
        total=len(results),
        passed_count=sum(item.status == "PASS" for item in results),
        warned_count=sum(item.status == "WARN" for item in results),
        blocked_count=sum(item.status == "BLOCK" for item in results),
        results=results,
    )


@router.get("/history", response_model=ValidationHistoryResponse)
def validation_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _principal: dict = Depends(require_scopes("sentinel:read")),
) -> ValidationHistoryResponse:
    """Return paginated validation history without account numbers or IBANs."""
    total = db.query(ValidationLog).count()
    rows = (
        db.query(ValidationLog)
        .order_by(ValidationLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ValidationHistoryResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            ValidationHistoryItem(
                id=row.id,
                created_at=row.created_at.isoformat(),
                sender_country=row.sender_country,
                recipient_country=row.recipient_country,
                recipient_name=row.recipient_name,
                currency=row.currency,
                amount=row.amount,
                reference=row.reference,
                status=row.status,
                risk_score=row.risk_score,
                passed=row.passed,
                execution_time_ms=row.execution_time_ms or 0.0,
            )
            for row in rows
        ],
    )
