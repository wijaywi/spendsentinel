from app.schemas.validation import PaymentValidationRequest
from app.database import Base
from app.models.validation_log import ValidationLog
from app.services.pre_transaction import PreTransactionValidator
from app.services.paypal_mock import PayPalMock
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_paypal_mock_dispute_due_date_is_ten_days_in_future() -> None:
    from datetime import datetime, timedelta

    before = datetime.utcnow()
    due = datetime.fromisoformat(
        PayPalMock().create_dispute("tx-1", "ITEM_NOT_RECEIVED")[
            "seller_response_due_date"
        ].removesuffix("Z")
    )
    delta = due - before
    assert timedelta(days=9, hours=23) < delta < timedelta(days=10, minutes=1)


def test_sanctions_keyword_is_review_only_not_an_authoritative_block() -> None:
    request = PaymentValidationRequest(
        sender_country="US",
        recipient_country="DE",
        recipient_name="Acme Iran office",
        iban="DE89370400440532013000",
        bic="DEUTDEFF",
        currency="EUR",
        amount=1250.50,
        reference="Invoice 2042",
    )

    result = PreTransactionValidator().validate(request)
    sanctions_check = next(
        check for check in result.checks
        if check.check_id == "sanctions_keyword_prescreen"
    )

    assert sanctions_check.severity == "WARNING"
    assert sanctions_check.passed is False
    assert sanctions_check.details["authoritative_screening"] is False
    assert result.status == "WARN"


def test_validation_without_database_cannot_pass_duplicate_check() -> None:
    request = PaymentValidationRequest(
        sender_country="US",
        recipient_country="DE",
        recipient_name="Acme GmbH",
        iban="DE89370400440532013000",
        bic="DEUTDEFF",
        currency="EUR",
        amount=1250.50,
        reference="INV-100",
    )

    result = PreTransactionValidator().validate(request)
    duplicate_check = next(
        check for check in result.checks if check.check_id == "duplicate_detection"
    )
    assert duplicate_check.passed is False
    assert duplicate_check.severity == "WARNING"
    assert result.status == "WARN"


def test_duplicate_detection_filters_candidates_in_the_database(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'validation.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            ValidationLog(
                id="existing-payment",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                sender_country="US",
                recipient_country="DE",
                recipient_name="Acme GmbH",
                currency="EUR",
                amount=1250.50,
                reference="INV-100",
                status="PASS",
                risk_score=0,
                passed=True,
                checks_results=[],
                recommendations=[],
            )
        )
        db.commit()
        request = PaymentValidationRequest(
            sender_country="US",
            recipient_country="DE",
            recipient_name=" acme gmbh ",
            iban="DE89370400440532013000",
            bic="DEUTDEFF",
            currency="EUR",
            amount=1250.50,
            reference=" inv-100 ",
        )
        result = PreTransactionValidator().validate(request, db=db)

    duplicate_check = next(
        check for check in result.checks if check.check_id == "duplicate_detection"
    )
    assert duplicate_check.passed is False
    assert duplicate_check.details["duplicate_id"] == "existing-payment"
    engine.dispose()


def test_invalid_iban_checksum_is_flagged() -> None:
    request = PaymentValidationRequest(
        sender_country="US",
        recipient_country="DE",
        recipient_name="Acme GmbH",
        iban="DE89370400440532013001",
        bic="DEUTDEFF",
        currency="EUR",
        amount=1250.50,
        reference="INV-100",
    )

    result = PreTransactionValidator().validate(request)
    iban_check = next(
        check for check in result.checks if check.check_id == "iban_validation"
    )

    assert iban_check.severity == "ERROR"
    assert iban_check.passed is False
