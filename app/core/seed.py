"""Database seed utility for SpendSentinel demo data and CE3.0 inspired scenarios."""

from datetime import datetime, timedelta
import uuid
from sqlalchemy.orm import Session
from app.models.evidence import (
    EvidenceRecordModel,
    DisputeResponseModel,
    AuditActivityModel,
    ValidationRecordModel,
    AgentTransactionModel,
    CorridorRiskModel,
)


def seed_database(db: Session) -> None:
    """Populate database with synthetic demo transactions, dispute records, and metrics.

    Sets up a complete Compelling Evidence 3.0 inspired testing scenario:
    - Customer `cust_alex_101` with device `dev_macbook_pro_01`
    - Prior Transaction 1 (180 days ago, delivered, confirmed, matching device & address)
    - Prior Transaction 2 (240 days ago, delivered, confirmed, matching device & address)
    - Current Transaction `tx_order_9981` (5 days ago, delivered, confirmed, matching device & address)
    - Validations, AI agent transactions, and corridor risk heatmaps.
    """
    # Check if already seeded
    if db.query(EvidenceRecordModel).count() > 0:
        return

    now = datetime.utcnow()

    # 1. CE3.0 Inspired Prior Transactions for cust_alex_101
    common_shipping = {
        "recipient_name": "Alex Mercer",
        "street": "742 Evergreen Terrace",
        "city": "Springfield",
        "state": "OR",
        "postal_code": "97477",
        "country": "US",
    }
    common_billing = {
        "street": "742 Evergreen Terrace",
        "city": "Springfield",
        "state": "OR",
        "postal_code": "97477",
        "country": "US",
    }
    common_device = {
        "device_id": "dev_macbook_pro_01",
        "ip_address": "198.51.100.24",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "screen_resolution": "2560x1600",
    }

    # Historical Txn 1 (180 days old)
    rec1 = EvidenceRecordModel(
        id=f"ev_{uuid.uuid4().hex[:16]}",
        transaction_id="tx_order_1001",
        customer_id="cust_alex_101",
        amount=145.50,
        currency="USD",
        timestamp=now - timedelta(days=180),
        created_at=now - timedelta(days=180),
        device_fingerprint=common_device,
        device_id="dev_macbook_pro_01",
        ip_address="198.51.100.24",
        shipping_address=common_shipping,
        billing_address=common_billing,
        billing_address_verified=True,
        delivery_tracking_number="1Z9999999999999991",
        delivery_carrier="UPS",
        delivery_status="DELIVERED",
        delivery_confirmed=True,
        item_description="Ergonomic Mechanical Keyboard",
        evidence_strength=100,
        strength_breakdown={
            "device_fingerprint": 20,
            "delivery_tracking": 15,
            "delivery_confirmed": 25,
            "prior_successful_transactions": 25,
            "billing_address_verified": 15,
        },
        prior_successful_transactions_count=2,
        version=1,
    )
    db.add(rec1)

    # Historical Txn 2 (240 days old)
    rec2 = EvidenceRecordModel(
        id=f"ev_{uuid.uuid4().hex[:16]}",
        transaction_id="tx_order_1002",
        customer_id="cust_alex_101",
        amount=89.00,
        currency="USD",
        timestamp=now - timedelta(days=240),
        created_at=now - timedelta(days=240),
        device_fingerprint=common_device,
        device_id="dev_macbook_pro_01",
        ip_address="198.51.100.24",
        shipping_address=common_shipping,
        billing_address=common_billing,
        billing_address_verified=True,
        delivery_tracking_number="1Z9999999999999992",
        delivery_carrier="UPS",
        delivery_status="DELIVERED",
        delivery_confirmed=True,
        item_description="Wireless Noise-Cancelling Headset",
        evidence_strength=100,
        strength_breakdown={
            "device_fingerprint": 20,
            "delivery_tracking": 15,
            "delivery_confirmed": 25,
            "prior_successful_transactions": 25,
            "billing_address_verified": 15,
        },
        prior_successful_transactions_count=2,
        version=1,
    )
    db.add(rec2)

    # Disputed Target Txn (5 days old)
    rec3 = EvidenceRecordModel(
        id=f"ev_{uuid.uuid4().hex[:16]}",
        transaction_id="tx_order_9981",
        customer_id="cust_alex_101",
        amount=299.99,
        currency="USD",
        timestamp=now - timedelta(days=5),
        created_at=now - timedelta(days=5),
        device_fingerprint=common_device,
        device_id="dev_macbook_pro_01",
        ip_address="198.51.100.24",
        shipping_address=common_shipping,
        billing_address=common_billing,
        billing_address_verified=True,
        delivery_tracking_number="1Z9999999999999993",
        delivery_carrier="UPS",
        delivery_status="DELIVERED",
        delivery_confirmed=True,
        item_description="4K UltraHD Studio Monitor",
        evidence_strength=100,
        strength_breakdown={
            "device_fingerprint": 20,
            "delivery_tracking": 15,
            "delivery_confirmed": 25,
            "prior_successful_transactions": 25,
            "billing_address_verified": 15,
        },
        prior_successful_transactions_count=2,
        version=1,
    )
    db.add(rec3)

    # Seed an auto-dispute response for tx_order_9981
    dr1 = DisputeResponseModel(
        id=f"dr_{uuid.uuid4().hex[:16]}",
        dispute_id="PP-D-8829104",
        transaction_id="tx_order_9981",
        confidence_score=95,
        recommended_action="CONTEST",
        action_reason=(
            "High confidence dispute defense package (95/100). Verified fulfillment tracking, "
            "device fingerprint identity, and 2 qualifying prior transactions satisfying CE3.0 "
            "inspired dispute deflection standards."
        ),
        evidence_package={
            "dispute_id": "PP-D-8829104",
            "transaction_id": "tx_order_9981",
            "qualifying_transactions_count": 2,
            "carrier_tracking": "1Z9999999999999993",
            "carrier": "UPS",
            "delivery_confirmed": True,
            "device_match": True,
        },
        ce3_compliance={
            "inspired_by": "Visa Compelling Evidence 3.0 adapted for PayPal",
            "qualifying_prior_transactions_count": 2,
            "requirement_met": True,
        },
        status="GENERATED",
        created_at=now - timedelta(hours=2),
    )
    db.add(dr1)

    # 2. Pre-Transaction Validation Records (PFPE)
    validations = [
        ("tx_val_01", "US->GB", "AVS_AND_CVV_CHECK", "PASS", 5, "AVS and CVV matched perfectly"),
        ("tx_val_02", "US->DE", "CORRIDOR_FX_DRIFT", "PASS", 12, "FX volatility within threshold"),
        ("tx_val_03", "US->ID", "VELOCITY_BURST", "WARN", 45, "Elevated frequency from IP subnet"),
        ("tx_val_04", "US->NG", "SANCTION_HIGH_RISK_PROXY", "BLOCK", 92, "Anonymizing Tor exit node detected"),
        ("tx_val_05", "US->CA", "CARD_EXPIRY_SANITY", "PASS", 8, "Card credentials valid"),
        ("tx_val_06", "US->BR", "ISSUER_DECLINE_SPIKE", "WARN", 55, "Elevated issuer rejection on corridor"),
        ("tx_val_07", "US->FR", "DEVICE_FINGERPRINT_SANITY", "PASS", 10, "Clean device trust score"),
        ("tx_val_08", "US->RU", "SANCTIONS_REGULATORY_SCREEN", "BLOCK", 98, "Restricted destination jurisdiction"),
    ]
    for tid, corr, rule, stat, rscore, msg in validations:
        v = ValidationRecordModel(
            id=f"val_{uuid.uuid4().hex[:12]}",
            transaction_id=tid,
            corridor=corr,
            rule_name=rule,
            status=stat,
            risk_score=rscore,
            message=msg,
            timestamp=now - timedelta(minutes=15),
        )
        db.add(v)

    # 3. Autonomous AI Agent Transactions (ACSO)
    agent_txs = [
        ("agent_procure_alpha", "tx_ag_01", 45.00, "USD", "APPROVE", "DAILY_BUDGET_CAP"),
        ("agent_procure_alpha", "tx_ag_02", 120.00, "USD", "APPROVE", "WHITELISTED_VENDOR"),
        ("agent_inventory_bot", "tx_ag_03", 850.00, "USD", "ESCALATE", "EXCEEDS_SINGLE_TRANSACTION_LIMIT"),
        ("agent_scraper_bot", "tx_ag_04", 15.00, "USD", "APPROVE", "SUBSCRIPTION_RENEWAL"),
        ("agent_rogue_test", "tx_ag_05", 2500.00, "USD", "DENY", "UNAPPROVED_RECIPIENT_OR_VENDOR"),
    ]
    for aid, tid, amt, curr, dec, pol in agent_txs:
        a = AgentTransactionModel(
            id=f"ag_{uuid.uuid4().hex[:12]}",
            agent_id=aid,
            transaction_id=tid,
            amount=amt,
            currency=curr,
            decision=dec,
            policy_checked=pol,
            timestamp=now - timedelta(hours=1),
        )
        db.add(a)

    # 4. Corridor Risk Matrix
    corridors = [
        ("US", "GB", "US-GB", 14200, 0.012, 0.004, 110, 15, "LOW_RISK"),
        ("US", "CA", "US-CA", 18500, 0.010, 0.003, 85, 12, "LOW_RISK"),
        ("US", "DE", "US-DE", 9800, 0.021, 0.006, 140, 22, "LOW_RISK"),
        ("US", "ID", "US-ID", 4300, 0.085, 0.028, 280, 58, "MODERATE_RISK"),
        ("US", "BR", "US-BR", 6100, 0.098, 0.035, 230, 64, "MODERATE_RISK"),
        ("US", "NG", "US-NG", 1900, 0.165, 0.072, 340, 84, "HIGH_RISK"),
        ("US", "SG", "US-SG", 7600, 0.018, 0.005, 190, 18, "LOW_RISK"),
    ]
    for src, tgt, code, vol, fail_rate, disp_rate, lat, rscore, cstat in corridors:
        c = CorridorRiskModel(
            id=f"corr_{code.lower()}",
            source_country=src,
            target_country=tgt,
            corridor_code=code,
            transaction_volume=vol,
            failure_rate=fail_rate,
            dispute_rate=disp_rate,
            avg_latency_ms=lat,
            risk_score=rscore,
            status=cstat,
            updated_at=now,
        )
        db.add(c)

    # 5. Recent Activity Logs
    logs = [
        ("EVIDENCE_VAULT", "EVIDENCE_STORED", "INFO", "tx_order_9981", "Proactive evidence captured for high-value order tx_order_9981"),
        ("DISPUTE_SHIELD", "DISPUTE_RESPONSE_GENERATED", "INFO", "PP-D-8829104", "Auto-deflected dispute PP-D-8829104 using CE3.0 inspired proof"),
        ("PRE_VALIDATION", "VALIDATION_PASSED", "INFO", "tx_val_01", "Cross-border AVS and CVV check passed for US-GB corridor"),
        ("PRE_VALIDATION", "VALIDATION_BLOCKED", "CRITICAL", "tx_val_04", "Blocked high-risk anonymized proxy on US-NG corridor"),
        ("AGENT_SECURITY", "POLICY_ESCALATED", "WARNING", "tx_ag_03", "AI Agent procurement requested $850.00 exceeding autonomous tier threshold"),
    ]
    for mod, evtype, sev, ref, summ in logs:
        log_entry = AuditActivityModel(
            id=f"act_{uuid.uuid4().hex[:12]}",
            module=mod,
            event_type=evtype,
            severity=sev,
            reference_id=ref,
            summary=summ,
            details={"source": "sentinel_auto_seed"},
            timestamp=now - timedelta(minutes=10),
        )
        db.add(log_entry)

    db.commit()
