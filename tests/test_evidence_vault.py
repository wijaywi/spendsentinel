import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.evidence import AuditActivityModel, EvidenceRecordModel
from app.schemas.evidence import TransactionEvidence
from app.services.evidence_vault import EvidenceVault


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _evidence(transaction_id: str, amount: float = 10.0) -> TransactionEvidence:
    return TransactionEvidence(
        transaction_id=transaction_id,
        customer_id=f"customer-{transaction_id}",
        amount=amount,
        device_fingerprint={"device_id": "device-1", "ip_address": "192.0.2.1"},
    )


def test_evidence_versions_are_monotonic_and_stats_use_database_aggregates(db) -> None:
    vault = EvidenceVault(db)
    first = vault.store_evidence(_evidence("tx-1", 10))
    second = vault.store_evidence(_evidence("tx-1", 15))
    vault.store_evidence(_evidence("tx-2", 20))

    assert (first.version, second.version) == (1, 2)
    assert second.parent_record_id == first.id
    stats = vault.get_evidence_stats()
    profile = vault.get_customer_profile({"device_id": "device-1"})
    assert stats["total_records"] == 3
    assert stats["distinct_transactions"] == 2
    assert profile["transaction_count"] == 2
    assert profile["total_spent"] == 35


def test_bulk_evidence_rolls_back_records_and_audit_entries_on_failure(db, monkeypatch) -> None:
    vault = EvidenceVault(db)
    original = vault._build_audit_activity
    calls = 0

    def fail_on_second(evidence, record):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated write failure")
        return original(evidence, record)

    monkeypatch.setattr(vault, "_build_audit_activity", fail_on_second)
    with pytest.raises(RuntimeError, match="simulated write failure"):
        vault.bulk_store_evidence([_evidence("tx-1"), _evidence("tx-2")])

    assert db.query(func.count(EvidenceRecordModel.id)).scalar() == 0
    assert db.query(func.count(AuditActivityModel.id)).scalar() == 0


def test_concurrent_evidence_writes_allocate_distinct_versions(tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent-vault.db'}",
        connect_args={"timeout": 15},
    )
    Base.metadata.create_all(engine)

    def store_version(_):
        with Session(engine) as session:
            return EvidenceVault(session).store_evidence(_evidence("shared-tx"))

    with ThreadPoolExecutor(max_workers=2) as workers:
        records = list(workers.map(store_version, range(2)))

    assert sorted(record.version for record in records) == [1, 2]
    with Session(engine) as session:
        stored = (
            session.query(EvidenceRecordModel)
            .filter(EvidenceRecordModel.transaction_id == "shared-tx")
            .all()
        )
        assert len(stored) == 2
        assert len({record.version for record in stored}) == 2
    engine.dispose()
