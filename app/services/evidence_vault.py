"""Evidence Vault and Dispute Prevention Service for SpendSentinel.

Proactively stores immutable transaction evidence and prepares dispute auto-responses
using an evidence-based framework inspired by Visa Compelling Evidence 3.0 principles
adapted for PayPal transactions.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_, select, text

from app.models.evidence import (
    EvidenceRecordModel,
    DisputeResponseModel,
    AuditActivityModel,
)
from app.schemas.evidence import (
    TransactionEvidence,
    EvidenceRecord,
    EvidenceSearchResult,
    DisputeAutoResponse,
)


class EvidenceVault:
    """Service managing immutable transaction evidence and automated dispute responses."""

    def __init__(self, db: Session) -> None:
        """Initialize the Evidence Vault with an active database session.

        Args:
            db: Active SQLAlchemy database session.
        """
        self.db = db

    def _calculate_evidence_strength(
        self,
        evidence: TransactionEvidence,
        prior_successful_count: int,
    ) -> tuple[int, Dict[str, int]]:
        """Calculate evidence strength score (0-100) based on completeness.

        Scoring weights:
        - Device fingerprint present: +20
        - Delivery tracking present: +15
        - Delivery confirmed: +25
        - 2+ prior successful transactions from same customer: +25 (CE3.0 inspired)
        - Billing address verified: +15

        Args:
            evidence: The transaction evidence payload.
            prior_successful_count: Number of previous successful transactions for customer.

        Returns:
            Tuple of (total_score, breakdown_dict).
        """
        breakdown: Dict[str, int] = {
            "device_fingerprint": 0,
            "delivery_tracking": 0,
            "delivery_confirmed": 0,
            "prior_successful_transactions": 0,
            "billing_address_verified": 0,
        }

        # 1. Device fingerprint present (+20)
        if evidence.device_fingerprint:
            dev_id = evidence.device_fingerprint.get("device_id")
            ip_addr = evidence.device_fingerprint.get("ip_address")
            if dev_id or ip_addr or len(evidence.device_fingerprint) > 0:
                breakdown["device_fingerprint"] = 20

        # 2. Delivery tracking present (+15)
        if evidence.delivery_tracking_number and evidence.delivery_tracking_number.strip():
            breakdown["delivery_tracking"] = 15

        # 3. Delivery confirmed (+25)
        if evidence.delivery_confirmed or (evidence.delivery_status and evidence.delivery_status.upper() in ("DELIVERED", "CONFIRMED")):
            breakdown["delivery_confirmed"] = 25

        # 4. 2+ prior successful transactions from same customer (+25)
        if prior_successful_count >= 2:
            breakdown["prior_successful_transactions"] = 25

        # 5. Billing address verified (+15)
        if evidence.billing_address_verified:
            breakdown["billing_address_verified"] = 15

        total = sum(breakdown.values())
        total_score = min(100, max(0, total))
        return total_score, breakdown

    def _extract_device_info(self, fingerprint: Optional[Dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
        """Extract device_id and ip_address from device fingerprint dictionary."""
        if not fingerprint:
            return None, None
        device_id = fingerprint.get("device_id") or fingerprint.get("deviceId")
        ip_address = fingerprint.get("ip_address") or fingerprint.get("ip") or fingerprint.get("ipAddress")
        return (str(device_id) if device_id else None, str(ip_address) if ip_address else None)

    def store_evidence(self, evidence: TransactionEvidence) -> EvidenceRecord:
        """Store transaction evidence in an append-only immutable vault record.

        If previous evidence exists for the transaction_id, a new version is created
        linking to the previous record ID to maintain a complete immutable audit trail.

        Args:
            evidence: The transaction evidence to persist.

        Returns:
            EvidenceRecord containing persisted data, version, and strength score.
        """
        self._lock_transaction(evidence.transaction_id)
        new_record = self._build_evidence_record(evidence)
        try:
            self.db.add(new_record)
            self.db.add(self._build_audit_activity(evidence, new_record))
            self.db.commit()
            self.db.refresh(new_record)
        except Exception:
            self.db.rollback()
            raise
        return self._to_pydantic_record(new_record)

    def _lock_transaction(self, transaction_id: str) -> None:
        """Serialize version assignment across workers before reading the latest version."""
        bind = self.db.get_bind()
        if bind.dialect.name == "sqlite" and not self.db.in_transaction():
            self.db.execute(text("BEGIN IMMEDIATE"))
        elif bind.dialect.name == "postgresql":
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:tx_id, 0))"),
                {"tx_id": transaction_id},
            )

    def _build_evidence_record(
        self, evidence: TransactionEvidence
    ) -> EvidenceRecordModel:
        # Count prior successful transactions for this customer
        prior_successful_count = (
            self.db.query(EvidenceRecordModel)
            .filter(
                EvidenceRecordModel.customer_id == evidence.customer_id,
                EvidenceRecordModel.transaction_id != evidence.transaction_id,
                or_(
                    EvidenceRecordModel.delivery_confirmed.is_(True),
                    EvidenceRecordModel.delivery_status.in_(["DELIVERED", "CONFIRMED", "COMPLETED"]),
                ),
            )
            .count()
        )

        # Compute evidence strength
        strength_score, breakdown = self._calculate_evidence_strength(evidence, prior_successful_count)

        # Check for existing records to maintain append-only versioning
        latest = (
            self.db.query(EvidenceRecordModel)
            .filter(EvidenceRecordModel.transaction_id == evidence.transaction_id)
            .order_by(EvidenceRecordModel.version.desc())
            .with_for_update()
            .first()
        )

        version = 1
        parent_id = evidence.parent_record_id
        if latest:
            version = latest.version + 1
            if not parent_id:
                parent_id = latest.id

        record_id = f"ev_{uuid.uuid4().hex[:16]}"
        tx_timestamp = evidence.timestamp or datetime.utcnow()
        now = datetime.utcnow()

        device_id, ip_address = self._extract_device_info(evidence.device_fingerprint)

        return EvidenceRecordModel(
            id=record_id,
            transaction_id=evidence.transaction_id,
            customer_id=evidence.customer_id,
            amount=evidence.amount,
            currency=evidence.currency,
            timestamp=tx_timestamp,
            created_at=now,
            device_fingerprint=evidence.device_fingerprint,
            device_id=device_id,
            ip_address=ip_address,
            shipping_address=evidence.shipping_address,
            billing_address=evidence.billing_address,
            billing_address_verified=evidence.billing_address_verified,
            delivery_tracking_number=evidence.delivery_tracking_number,
            delivery_carrier=evidence.delivery_carrier,
            delivery_status=evidence.delivery_status,
            delivery_confirmed=evidence.delivery_confirmed,
            item_description=evidence.item_description,
            evidence_strength=strength_score,
            strength_breakdown=breakdown,
            prior_successful_transactions_count=prior_successful_count,
            parent_record_id=parent_id,
            version=version,
            extra_metadata=evidence.metadata,
        )

    @staticmethod
    def _build_audit_activity(
        evidence: TransactionEvidence, new_record: EvidenceRecordModel
    ) -> AuditActivityModel:
        return AuditActivityModel(
            id=f"act_{uuid.uuid4().hex[:16]}",
            module="EVIDENCE_VAULT",
            event_type="EVIDENCE_STORED",
            severity="INFO",
            reference_id=evidence.transaction_id,
            summary=(
                f"Stored immutable evidence v{new_record.version} for transaction "
                f"{evidence.transaction_id} (Score: {new_record.evidence_strength}/100)"
            ),
            details={
                "record_id": new_record.id,
                "version": new_record.version,
                "strength_score": new_record.evidence_strength,
                "customer_id": evidence.customer_id,
                "amount": evidence.amount,
                "delivery_confirmed": evidence.delivery_confirmed,
            },
            timestamp=new_record.created_at,
        )

    def search_evidence(self, transaction_id: str) -> EvidenceSearchResult:
        """Search the Evidence Vault for all evidence records linked to a transaction.

        Provides a contestability assessment based on evidence completeness.

        Args:
            transaction_id: The PayPal transaction ID.

        Returns:
            EvidenceSearchResult containing latest record, version history, and contestability assessment.
        """
        records = (
            self.db.query(EvidenceRecordModel)
            .filter(EvidenceRecordModel.transaction_id == transaction_id)
            .order_by(EvidenceRecordModel.created_at.asc())
            .all()
        )

        if not records:
            return EvidenceSearchResult(
                transaction_id=transaction_id,
                evidence_found=False,
                latest_record=None,
                history_records=[],
                evidence_strength=0,
                contestability_status="INSUFFICIENT_EVIDENCE",
                contestability_summary="No evidence records found in vault for this transaction.",
                qualifying_ce3_factors=[],
            )

        history_pydantic = [self._to_pydantic_record(r) for r in records]
        latest_record = history_pydantic[-1]
        strength = latest_record.evidence_strength

        # Contestability categorization
        if strength >= 70:
            contestability_status = "HIGHLY_CONTESTABLE"
            contestability_summary = "Strong evidence package assembled. Proactive dispute defense recommended."
        elif strength >= 40:
            contestability_status = "MODERATELY_CONTESTABLE"
            contestability_summary = "Partial evidence available. Manual agent review or escalation recommended."
        else:
            contestability_status = "LOW_CONTESTABILITY"
            contestability_summary = "Insufficient fulfillment or device proof. Accepting dispute advised to minimize fees."

        # Identify qualifying factors
        factors: List[str] = []
        if latest_record.device_fingerprint:
            factors.append("Device fingerprint and IP identity registered")
        if latest_record.delivery_tracking_number:
            factors.append(f"Carrier tracking logged: {latest_record.delivery_carrier or 'Standard'}")
        if latest_record.delivery_confirmed:
            factors.append("Delivery status confirmed by carrier")
        if latest_record.prior_successful_transactions_count >= 2:
            factors.append(f"Customer has {latest_record.prior_successful_transactions_count} prior successful orders (CE3.0 inspired proof)")
        if latest_record.billing_address_verified:
            factors.append("AVS billing address verified")

        return EvidenceSearchResult(
            transaction_id=transaction_id,
            evidence_found=True,
            latest_record=latest_record,
            history_records=history_pydantic,
            evidence_strength=strength,
            contestability_status=contestability_status,
            contestability_summary=contestability_summary,
            qualifying_ce3_factors=factors,
        )

    def prepare_dispute_response(self, dispute_id: str, transaction_id: str) -> DisputeAutoResponse:
        """Prepare an automated dispute response package inspired by Visa Compelling Evidence 3.0 principles.

        Evaluates prior customer transaction history (120-365 days window), matching
        device identifiers and IP addresses, and physical delivery confirmation.

        Args:
            dispute_id: The PayPal Dispute ID.
            transaction_id: The disputed transaction ID.

        Returns:
            DisputeAutoResponse with confidence score, recommended action (CONTEST, ESCALATE, ACCEPT),
            and structured JSON evidence package.
        """
        # Retrieve target transaction evidence
        latest_model = (
            self.db.query(EvidenceRecordModel)
            .filter(EvidenceRecordModel.transaction_id == transaction_id)
            .order_by(EvidenceRecordModel.version.desc())
            .first()
        )

        now = datetime.utcnow()

        if not latest_model:
            # When no evidence exists in vault
            pkg = {
                "transaction_id": transaction_id,
                "dispute_id": dispute_id,
                "status": "NO_EVIDENCE_FOUND",
                "notes": "No transaction evidence was proactively captured in the vault.",
            }
            return DisputeAutoResponse(
                dispute_id=dispute_id,
                transaction_id=transaction_id,
                confidence_score=10,
                recommended_action="ACCEPT",
                action_reason="Insufficient evidence: No proactive records exist in Evidence Vault.",
                evidence_package=pkg,
                ce3_compliance={
                    "inspired_by": "Visa Compelling Evidence 3.0 adapted for PayPal",
                    "qualifying_prior_transactions_count": 0,
                    "requirement_met": False,
                },
                generated_at=now,
            )

        # Search matching prior transactions by same customer OR same device fingerprint
        tx_time = latest_model.timestamp or latest_model.created_at
        device_id = latest_model.device_id
        ip_addr = latest_model.ip_address
        customer_id = latest_model.customer_id
        shipping_addr = latest_model.shipping_address or {}

        # Look up prior transactions from same customer or device
        query_conditions = [EvidenceRecordModel.customer_id == customer_id]
        if device_id:
            query_conditions.append(EvidenceRecordModel.device_id == device_id)
        if ip_addr:
            query_conditions.append(EvidenceRecordModel.ip_address == ip_addr)

        candidates = (
            self.db.query(EvidenceRecordModel)
            .filter(
                EvidenceRecordModel.transaction_id != transaction_id,
                or_(*query_conditions),
            )
            .order_by(EvidenceRecordModel.timestamp.desc())
            .all()
        )

        # De-duplicate transactions (keep latest version per transaction)
        seen_tx: Dict[str, EvidenceRecordModel] = {}
        for c in candidates:
            if c.transaction_id not in seen_tx or c.version > seen_tx[c.transaction_id].version:
                seen_tx[c.transaction_id] = c
        prior_records = list(seen_tx.values())

        # Evaluate CE3.0 inspired criteria:
        # 1. 2+ prior successful transactions
        # 2. Window: 120 - 365 days old (or flag qualified historical orders)
        # 3. Matching device_id / IP address
        # 4. Matching shipping address or account/customer_id
        qualifying_prior_txns: List[Dict[str, Any]] = []
        recent_matching_txns: List[Dict[str, Any]] = []

        for p in prior_records:
            p_time = p.timestamp or p.created_at
            age_days = (tx_time - p_time).days if tx_time > p_time else 0

            device_match = (
                (bool(device_id) and p.device_id == device_id) or
                (bool(ip_addr) and p.ip_address == ip_addr)
            )
            address_match = (
                p.customer_id == customer_id or
                (bool(shipping_addr) and p.shipping_address == shipping_addr)
            )
            delivery_ok = (
                p.delivery_confirmed or
                (p.delivery_status and p.delivery_status.upper() in ["DELIVERED", "CONFIRMED", "COMPLETED"])
            )

            tx_info = {
                "transaction_id": p.transaction_id,
                "timestamp": p_time.isoformat(),
                "age_days": age_days,
                "amount": p.amount,
                "currency": p.currency,
                "device_id_match": bool(device_id and p.device_id == device_id),
                "ip_address_match": bool(ip_addr and p.ip_address == ip_addr),
                "delivery_confirmed": p.delivery_confirmed,
                "delivery_tracking_number": p.delivery_tracking_number,
                "delivery_carrier": p.delivery_carrier,
            }

            if delivery_ok and (device_match or address_match):
                if 120 <= age_days <= 365:
                    qualifying_prior_txns.append(tx_info)
                else:
                    recent_matching_txns.append(tx_info)

        ce3_criteria_met = len(qualifying_prior_txns) >= 2

        # Confidence calculation (0 - 100)
        confidence = 0
        points_breakdown = {}

        # 1. CE3.0 inspired historical transactions match
        if ce3_criteria_met:
            confidence += 40
            points_breakdown["ce3_qualifying_transactions"] = 40
        elif len(qualifying_prior_txns) == 1:
            confidence += 20
            points_breakdown["ce3_qualifying_transactions"] = 20
        elif len(recent_matching_txns) >= 2:
            confidence += 25
            points_breakdown["ce3_recent_matching_transactions"] = 25

        # 2. Delivery confirmation on disputed transaction
        if latest_model.delivery_confirmed:
            confidence += 25
            points_breakdown["delivery_confirmed"] = 25
        elif latest_model.delivery_tracking_number:
            confidence += 15
            points_breakdown["delivery_tracking_present"] = 15

        # 3. Device & IP fingerprint present
        if latest_model.device_id or latest_model.ip_address:
            confidence += 15
            points_breakdown["device_fingerprint_present"] = 15

        # 4. AVS billing address verification
        if latest_model.billing_address_verified:
            confidence += 10
            points_breakdown["billing_address_verified"] = 10

        # 5. Prior customer relationship
        if len(prior_records) >= 2:
            confidence += 10
            points_breakdown["established_customer_relationship"] = 10

        confidence = min(100, max(0, confidence))

        # Recommended action rule:
        # CONTEST if confidence >= 70 and has strong device/delivery match
        # ESCALATE if confidence 40 - 70
        # ACCEPT if confidence < 40 (evidence too weak)
        has_strong_delivery_or_device = (
            latest_model.delivery_confirmed or
            (latest_model.delivery_tracking_number and (latest_model.device_id or latest_model.ip_address))
        )

        if confidence >= 70 and has_strong_delivery_or_device:
            recommended_action = "CONTEST"
            action_reason = (
                f"High confidence dispute defense package ({confidence}/100). Verified fulfillment tracking, "
                f"device fingerprint identity, and {len(qualifying_prior_txns)} qualifying prior transactions "
                "satisfying CE3.0 inspired dispute deflection standards."
            )
        elif confidence >= 40:
            recommended_action = "ESCALATE"
            action_reason = (
                f"Moderate confidence defense package ({confidence}/100). Evidence is partially verified. "
                "Recommend human merchant review or manual escalation before submission."
            )
        else:
            recommended_action = "ACCEPT"
            action_reason = (
                f"Low confidence defense package ({confidence}/100). Available evidence does not satisfy "
                "deflection criteria. Accepting claim prevents dispute penalty fees."
            )

        # Structured evidence package
        evidence_package = {
            "dispute_id": dispute_id,
            "disputed_transaction": {
                "transaction_id": latest_model.transaction_id,
                "customer_id": latest_model.customer_id,
                "amount": latest_model.amount,
                "currency": latest_model.currency,
                "timestamp": latest_model.timestamp.isoformat() if latest_model.timestamp else None,
                "item_description": latest_model.item_description,
            },
            "defense_narrative": (
                f"Automated merchant rebuttal package for PayPal dispute {dispute_id}. "
                "Merchant has provided proactive proof of fulfillment, verified device and IP identity, "
                "and demonstrated an undisputed prior commercial relationship with the buyer."
            ),
            "fulfillment_evidence": {
                "carrier": latest_model.delivery_carrier,
                "tracking_number": latest_model.delivery_tracking_number,
                "status": latest_model.delivery_status,
                "confirmed_delivered": latest_model.delivery_confirmed,
                "shipping_address": latest_model.shipping_address,
            },
            "identity_evidence": {
                "device_id": latest_model.device_id,
                "ip_address": latest_model.ip_address,
                "billing_address_verified": latest_model.billing_address_verified,
            },
            "ce3_inspired_evidence": {
                "compliance_model": "Visa Compelling Evidence 3.0 inspired dispute support for SpendSentinel",
                "qualifying_transactions_120_to_365_days": qualifying_prior_txns,
                "recent_supportive_transactions": recent_matching_txns,
                "qualifying_transactions_count": len(qualifying_prior_txns),
                "device_or_ip_match": any(t["device_id_match"] or t["ip_address_match"] for t in qualifying_prior_txns + recent_matching_txns),
            },
            "scoring_breakdown": points_breakdown,
        }

        ce3_compliance_meta = {
            "inspired_by": "Visa Compelling Evidence 3.0 adapted for PayPal",
            "qualifying_prior_transactions_count": len(qualifying_prior_txns),
            "qualifying_window_days": "120-365",
            "requirement_met": ce3_criteria_met,
            "strong_device_delivery_match": has_strong_delivery_or_device,
        }

        # Persist dispute response
        dr_model = DisputeResponseModel(
            id=f"dr_{uuid.uuid4().hex[:16]}",
            dispute_id=dispute_id,
            transaction_id=transaction_id,
            confidence_score=confidence,
            recommended_action=recommended_action,
            action_reason=action_reason,
            evidence_package=evidence_package,
            ce3_compliance=ce3_compliance_meta,
            status="GENERATED",
            created_at=now,
        )
        self.db.add(dr_model)

        # Audit log
        audit_entry = AuditActivityModel(
            id=f"act_{uuid.uuid4().hex[:16]}",
            module="DISPUTE_SHIELD",
            event_type="DISPUTE_RESPONSE_GENERATED",
            severity="INFO" if recommended_action == "CONTEST" else "WARNING",
            reference_id=dispute_id,
            summary=f"Generated auto-response for dispute {dispute_id} -> Action: {recommended_action} (Confidence: {confidence}/100)",
            details={
                "dispute_id": dispute_id,
                "transaction_id": transaction_id,
                "recommended_action": recommended_action,
                "confidence_score": confidence,
            },
            timestamp=now,
        )
        self.db.add(audit_entry)
        self.db.commit()

        return DisputeAutoResponse(
            dispute_id=dispute_id,
            transaction_id=transaction_id,
            confidence_score=confidence,
            recommended_action=recommended_action,
            action_reason=action_reason,
            evidence_package=evidence_package,
            ce3_compliance=ce3_compliance_meta,
            generated_at=now,
        )

    def get_customer_profile(self, device_fingerprint: Dict[str, Any]) -> Dict[str, Any]:
        """Search for all transactions with matching device_id or IP address.

        Returns customer transaction count, dispute rate, and average order value.

        Args:
            device_fingerprint: Dictionary with device_id, ip_address, or other telemetry.

        Returns:
            Dictionary profile with transaction count, dispute rate, and order analytics.
        """
        device_id, ip_addr = self._extract_device_info(device_fingerprint)

        query_conditions = []
        if device_id:
            query_conditions.append(EvidenceRecordModel.device_id == device_id)
        if ip_addr:
            query_conditions.append(EvidenceRecordModel.ip_address == ip_addr)

        if not query_conditions:
            return {
                "device_id": None,
                "ip_address": None,
                "transaction_count": 0,
                "dispute_count": 0,
                "dispute_rate": 0.0,
                "average_order_value": 0.0,
                "total_spent": 0.0,
                "first_seen": None,
                "last_seen": None,
                "associated_customers": [],
                "risk_assessment": "UNKNOWN",
            }

        latest_versions = self._latest_versions_subquery()
        matching = (
            self.db.query(EvidenceRecordModel)
            .join(
                latest_versions,
                (EvidenceRecordModel.transaction_id == latest_versions.c.transaction_id)
                & (EvidenceRecordModel.version == latest_versions.c.latest_version),
            )
            .filter(or_(*query_conditions))
        )
        tx_count = matching.count()
        if tx_count == 0:
            return {
                "device_id": device_id,
                "ip_address": ip_addr,
                "transaction_count": 0,
                "dispute_count": 0,
                "dispute_rate": 0.0,
                "average_order_value": 0.0,
                "total_spent": 0.0,
                "first_seen": None,
                "last_seen": None,
                "associated_customers": [],
                "risk_assessment": "LOW",
            }

        profile = matching.with_entities(
            func.sum(EvidenceRecordModel.amount),
            func.avg(EvidenceRecordModel.amount),
            func.min(EvidenceRecordModel.timestamp),
            func.max(EvidenceRecordModel.timestamp),
        ).one()
        total_spent, avg_order_value, first_seen, last_seen = profile
        customer_rows = (
            matching.with_entities(EvidenceRecordModel.customer_id)
            .distinct()
            .limit(101)
            .all()
        )
        associated_customers = [row[0] for row in customer_rows[:100]]
        dispute_count = (
            self.db.query(func.count(DisputeResponseModel.id))
            .join(
                latest_versions,
                DisputeResponseModel.transaction_id == latest_versions.c.transaction_id,
            )
            .join(
                EvidenceRecordModel,
                (EvidenceRecordModel.transaction_id == latest_versions.c.transaction_id)
                & (EvidenceRecordModel.version == latest_versions.c.latest_version),
            )
            .filter(or_(*query_conditions))
            .scalar()
            or 0
        )

        dispute_rate = round(dispute_count / tx_count, 4)

        if dispute_rate >= 0.15:
            risk_assessment = "HIGH"
        elif dispute_rate >= 0.05:
            risk_assessment = "MEDIUM"
        else:
            risk_assessment = "LOW"

        return {
            "device_id": device_id,
            "ip_address": ip_addr,
            "transaction_count": tx_count,
            "dispute_count": dispute_count,
            "dispute_rate": dispute_rate,
            "average_order_value": avg_order_value,
            "total_spent": round(total_spent, 2),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "associated_customers": associated_customers,
            "associated_customers_truncated": len(customer_rows) > 100,
            "risk_assessment": risk_assessment,
        }

    def bulk_store_evidence(self, evidences: List[TransactionEvidence]) -> List[EvidenceRecord]:
        """Store multiple transaction evidence payloads atomically.

        Args:
            evidences: List of TransactionEvidence items.

        Returns:
            List of stored EvidenceRecord objects.
        """
        if not evidences:
            return []
        results: List[EvidenceRecordModel] = []
        try:
            for evidence in evidences:
                self._lock_transaction(evidence.transaction_id)
                record = self._build_evidence_record(evidence)
                self.db.add(record)
                self.db.add(self._build_audit_activity(evidence, record))
                self.db.flush()
                results.append(record)
            self.db.commit()
            for record in results:
                self.db.refresh(record)
        except Exception:
            self.db.rollback()
            raise
        return [self._to_pydantic_record(record) for record in results]

    def get_evidence_stats(self) -> Dict[str, Any]:
        """Retrieve aggregate statistics for the Evidence Vault.

        Returns:
            Dictionary with total_records, avg_evidence_strength, and auto_contestable_count.
        """
        total_records = self.db.query(func.count(EvidenceRecordModel.id)).scalar() or 0
        latest_versions = self._latest_versions_subquery()
        latest_stats = (
            self.db.query(
                func.count(EvidenceRecordModel.id),
                func.avg(EvidenceRecordModel.evidence_strength),
                func.sum(case((EvidenceRecordModel.evidence_strength >= 70, 1), else_=0)),
            )
            .join(
                latest_versions,
                (EvidenceRecordModel.transaction_id == latest_versions.c.transaction_id)
                & (EvidenceRecordModel.version == latest_versions.c.latest_version),
            )
            .one()
        )
        distinct_count, average, contestable = latest_stats
        dispute_stats = self.db.query(
            func.count(DisputeResponseModel.id),
            func.sum(case((DisputeResponseModel.recommended_action == "CONTEST", 1), else_=0)),
            func.sum(case((DisputeResponseModel.recommended_action == "ESCALATE", 1), else_=0)),
            func.sum(case((DisputeResponseModel.recommended_action == "ACCEPT", 1), else_=0)),
        ).one()
        dispute_count, contest, escalate, accept = dispute_stats
        action_breakdown = {
            "CONTEST": contest or 0,
            "ESCALATE": escalate or 0,
            "ACCEPT": accept or 0,
        }

        return {
            "total_records": total_records,
            "distinct_transactions": distinct_count or 0,
            "avg_evidence_strength": round(float(average or 0), 2),
            "auto_contestable_count": contestable or 0,
            "total_dispute_responses": dispute_count or 0,
            "action_breakdown": action_breakdown,
        }

    def _latest_versions_subquery(self):
        return (
            self.db.query(
                EvidenceRecordModel.transaction_id.label("transaction_id"),
                func.max(EvidenceRecordModel.version).label("latest_version"),
            )
            .group_by(EvidenceRecordModel.transaction_id)
            .subquery()
        )

    def _to_pydantic_record(self, model: EvidenceRecordModel) -> EvidenceRecord:
        """Convert an EvidenceRecordModel SQLAlchemy instance to a Pydantic EvidenceRecord."""
        return EvidenceRecord(
            id=model.id,
            transaction_id=model.transaction_id,
            customer_id=model.customer_id,
            amount=model.amount,
            currency=model.currency,
            timestamp=model.timestamp,
            created_at=model.created_at,
            device_fingerprint=model.device_fingerprint,
            shipping_address=model.shipping_address,
            billing_address=model.billing_address,
            billing_address_verified=model.billing_address_verified,
            delivery_tracking_number=model.delivery_tracking_number,
            delivery_carrier=model.delivery_carrier,
            delivery_status=model.delivery_status,
            delivery_confirmed=model.delivery_confirmed,
            item_description=model.item_description,
            evidence_strength=model.evidence_strength,
            strength_breakdown=model.strength_breakdown,
            prior_successful_transactions_count=model.prior_successful_transactions_count,
            parent_record_id=model.parent_record_id,
            version=model.version,
            metadata=model.extra_metadata,
        )
