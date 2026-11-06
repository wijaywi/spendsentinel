from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.validation import _validate_and_log
from app.database import Base
from app.models.validation_log import ValidationLog
from app.schemas.validation import PaymentValidationRequest


def test_validation_log_does_not_store_account_numbers_or_iban() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    payment = PaymentValidationRequest(
        sender_country="US",
        recipient_country="DE",
        recipient_name="Acme GmbH",
        iban="DE89370400440532013000",
        bic="DEUTDEFF",
        currency="EUR",
        amount=1250.50,
        reference="INV-100",
    )

    with session_factory() as session:
        _validate_and_log(payment, session)
        record = session.query(ValidationLog).one()

        assert record.iban is None
        assert record.recipient_account is None
        assert "DE89370400440532013000" not in str(record.checks_results)

    engine.dispose()
