"""
Pre-Transaction Validation Service for SpendSentinel.

Executes sequential, deterministic checks across IBAN checksums, BIC formatting,
currency compliance, corridor risk, timing schedules, duplicate detection,
sanctions keywords, and SWIFT character sets before transaction dispatch.
"""

from datetime import datetime, timedelta, timezone
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.iban_registry import format_iban, is_iban_country, validate_iban
from app.data.swift_codes import format_bic, get_bank_info, validate_bic
from app.data.currencies import check_currency_pair_support, get_currency_info, validate_currency
from app.data.corridors import get_corridor_risk, get_optimal_send_time
from app.models.validation_log import ValidationLog
from app.schemas.validation import CheckItem, PaymentValidationRequest, ValidationResult

# SWIFT MT103 Field 70 allowed character set (SWIFT X-Character set)
# Allowed: a-z, A-Z, 0-9, space, / - ? : ( ) . , ' +
SWIFT_X_ALLOWED_REGEX = re.compile(r"^[A-Za-z0-9/\-?:().,'+ ]*$")

# Known false-positive phrases containing sensitive geographic or historical terms
SANCTIONS_FALSE_POSITIVES = {
    "persian rug": "Persian rug or traditional handwoven carpet",
    "persian carpet": "Traditional handwoven carpet",
    "persian cat": "Domestic feline pedigree",
    "cuban coffee": "Specialty roast coffee blend",
    "cuban sandwich": "Catering or culinary invoice",
    "damascus steel": "Pattern-welded metallurgy steel blade",
    "damascus knife": "Pattern-welded kitchen knife",
    "sudan grass": "Agricultural forage seed",
}

# Heuristic terms that require review and are not authoritative sanctions matches
PROHIBITED_SANCTIONS_TERMS: Set[str] = {
    "cuba",
    "havana",
    "iran",
    "tehran",
    "north korea",
    "pyongyang",
    "dprk",
    "syria",
    "damascus",
    "crimea",
    "sevastopol",
    "donetsk",
    "luhansk",
    "hezbollah",
    "hamas",
    "taliban",
    "al-qaeda",
    "isis",
    "daesh",
    "specially designated",
    "ofac sdn",
}

# Global reserve settlement currencies accepted by multi-currency clearing systems
GLOBAL_SETTLEMENT_CURRENCIES = {"USD", "EUR", "GBP"}


class PreTransactionValidator:
    """
    Validation engine evaluating payment requests against 10 comprehensive risk criteria.
    """

    def __init__(self) -> None:
        """Initialize the validator instance."""
        pass

    def validate(
        self,
        request: PaymentValidationRequest,
        db: Optional[Session] = None,
    ) -> ValidationResult:
        """
        Execute all pre-transaction validation rules in sequence.

        Args:
            request: The payment request payload to evaluate.
            db: Optional SQLAlchemy database session for duplicate checking and audit persistence.

        Returns:
            ValidationResult with composite risk score, decision status, check items, and recommendations.
        """
        start_time = time.perf_counter()
        validation_id = f"sentinel-{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc)

        checks: List[CheckItem] = []
        recommendations: List[str] = []

        # ---------------------------------------------------------
        # Check a: IBAN format and checksum validation
        # ---------------------------------------------------------
        iban_check, iban_rec = self._check_iban(request)
        checks.append(iban_check)
        if iban_rec:
            recommendations.append(iban_rec)

        # ---------------------------------------------------------
        # Check b: SWIFT/BIC format validation
        # ---------------------------------------------------------
        bic_check, bic_rec = self._check_bic(request)
        checks.append(bic_check)
        if bic_rec:
            recommendations.append(bic_rec)

        # ---------------------------------------------------------
        # Check c: Currency code validation (ISO 4217)
        # ---------------------------------------------------------
        curr_check, curr_rec = self._check_currency_code(request)
        checks.append(curr_check)
        if curr_rec:
            recommendations.append(curr_rec)

        # ---------------------------------------------------------
        # Check d: Currency-country compatibility
        # ---------------------------------------------------------
        compat_check, compat_rec = self._check_currency_country_compat(request)
        checks.append(compat_check)
        if compat_rec:
            recommendations.append(compat_rec)

        # ---------------------------------------------------------
        # Check e: Amount validation
        # ---------------------------------------------------------
        amt_check, amt_rec = self._check_amount(request)
        checks.append(amt_check)
        if amt_rec:
            recommendations.append(amt_rec)

        # ---------------------------------------------------------
        # Check f: Corridor risk assessment
        # ---------------------------------------------------------
        corridor_check, corridor_rec = self._check_corridor(request)
        checks.append(corridor_check)
        if corridor_rec:
            recommendations.append(corridor_rec)

        # ---------------------------------------------------------
        # Check g: Timing check
        # ---------------------------------------------------------
        timing_check, timing_rec = self._check_timing(request, now_utc)
        checks.append(timing_check)
        if timing_rec:
            recommendations.append(timing_rec)

        # ---------------------------------------------------------
        # Check h: Duplicate detection
        # ---------------------------------------------------------
        dup_check, dup_rec = self._check_duplicate(request, db, now_utc)
        checks.append(dup_check)
        if dup_rec:
            recommendations.append(dup_rec)

        # ---------------------------------------------------------
        # Check i: Sanctions keyword pre-screen
        # ---------------------------------------------------------
        sanct_check, sanct_rec = self._check_sanctions(request)
        checks.append(sanct_check)
        if sanct_rec:
            recommendations.append(sanct_rec)

        # ---------------------------------------------------------
        # Check j: Reference format check
        # ---------------------------------------------------------
        ref_check, ref_rec = self._check_reference(request)
        checks.append(ref_check)
        if ref_rec:
            recommendations.append(ref_rec)

        # ---------------------------------------------------------
        # Composite risk calculation
        # ---------------------------------------------------------
        raw_score = sum(c.score_impact for c in checks)
        risk_score = max(0, min(100, raw_score))

        # Status determination:
        # PASS: score < 30
        # WARN: 30 <= score <= 70
        # BLOCK: score > 70
        if risk_score < 30:
            status = "PASS"
            summary_narrative = (
                f"Validation passed with low risk score ({risk_score}/100). "
                f"Account format, routing, and corridor parameters are within acceptable thresholds."
            )
        elif risk_score <= 70:
            status = "WARN"
            summary_narrative = (
                f"Validation completed with warnings (Risk Score: {risk_score}/100). "
                f"Review actionable recommendations to prevent potential settlement delays or correspondent fees."
            )
        else:
            status = "BLOCK"
            summary_narrative = (
                f"Payment blocked by pre-transaction safeguard (Risk Score: {risk_score}/100). "
                f"Critical compliance, formatting, or duplicate validation errors detected."
            )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return ValidationResult(
            validation_id=validation_id,
            timestamp=now_utc.isoformat(),
            status=status,
            risk_score=risk_score,
            is_blocked=(status == "BLOCK"),
            sender_country=request.sender_country,
            recipient_country=request.recipient_country,
            currency=request.currency,
            amount=request.amount,
            reference=request.reference,
            checks=checks,
            recommendations=recommendations,
            summary=summary_narrative,
            execution_time_ms=elapsed_ms,
        )

    # -------------------------------------------------------------
    # Internal Rule Check Implementations
    # -------------------------------------------------------------

    def _check_iban(self, request: PaymentValidationRequest) -> Tuple[CheckItem, Optional[str]]:
        """Check a: Validate IBAN format, jurisdiction rules, and MOD-97-10 checksum."""
        country = request.recipient_country.upper()
        country_requires_iban = is_iban_country(country)

        # Case 1: Recipient country requires IBAN but none provided
        if not request.iban:
            if country_requires_iban:
                return (
                    CheckItem(
                        check_id="iban_validation",
                        name="IBAN Format and Checksum",
                        passed=False,
                        severity="ERROR",
                        score_impact=75,
                        message=(
                            f"Recipient country '{country}' strictly mandates an IBAN for electronic bank transfers, "
                            f"but no IBAN was provided."
                        ),
                        details={"country": country, "iban_required": True},
                    ),
                    f"Obtain the beneficiary's {country} IBAN prior to dispatch. Transactions to {country} lacking an IBAN are rejected.",
                )
            # IBAN not mandatory (e.g. US, CA, AU) and not provided
            return (
                CheckItem(
                    check_id="iban_validation",
                    name="IBAN Format and Checksum",
                    passed=True,
                    severity="INFO",
                    score_impact=0,
                    message=f"Country '{country}' uses national clearing accounts rather than mandatory IBAN.",
                    details={"country": country, "iban_required": False},
                ),
                None,
            )

        # Case 2: IBAN is provided
        cleaned_iban = format_iban(request.iban)
        is_valid, reason = validate_iban(cleaned_iban)

        if not is_valid:
            return (
                CheckItem(
                    check_id="iban_validation",
                    name="IBAN Format and Checksum",
                    passed=False,
                    severity="ERROR",
                    score_impact=75,
                    message=reason,
                    details={"iban": cleaned_iban, "is_valid": False},
                ),
                "Verify beneficiary account number and recalculate check digits to fix IBAN validation error.",
            )

        # Check prefix country alignment
        iban_prefix = cleaned_iban[:2]
        if iban_prefix != country:
            return (
                CheckItem(
                    check_id="iban_validation",
                    name="IBAN Format and Checksum",
                    passed=True,
                    severity="WARNING",
                    score_impact=15,
                    message=(
                        f"IBAN country prefix '{iban_prefix}' differs from intended destination country '{country}'."
                    ),
                    details={"iban_prefix": iban_prefix, "recipient_country": country},
                ),
                f"Confirm if beneficiary bank account is domiciled in {iban_prefix} instead of {country} to prevent misrouting.",
            )

        return (
            CheckItem(
                check_id="iban_validation",
                name="IBAN Format and Checksum",
                passed=True,
                severity="INFO",
                score_impact=0,
                message=reason,
                details={"iban": cleaned_iban, "is_valid": True},
            ),
            None,
        )

    def _check_bic(self, request: PaymentValidationRequest) -> Tuple[CheckItem, Optional[str]]:
        """Check b: Validate SWIFT/BIC structure and recipient country consistency."""
        if not request.bic:
            # BIC not provided
            return (
                CheckItem(
                    check_id="bic_validation",
                    name="SWIFT/BIC Code Validation",
                    passed=True,
                    severity="WARNING",
                    score_impact=15,
                    message="No SWIFT/BIC provided. International payments routed without BIC incur higher intermediary search fees.",
                    details={"bic": None},
                ),
                "Provide receiving bank SWIFT/BIC to ensure straight-through processing (STP) and avoid intermediary search deductions.",
            )

        cleaned_bic = format_bic(request.bic)
        is_valid, reason = validate_bic(cleaned_bic)

        if not is_valid:
            return (
                CheckItem(
                    check_id="bic_validation",
                    name="SWIFT/BIC Code Validation",
                    passed=False,
                    severity="ERROR",
                    score_impact=40,
                    message=reason,
                    details={"bic": cleaned_bic, "is_valid": False},
                ),
                "Supply a valid 8 or 11 character ISO 9362 SWIFT/BIC code for the receiving bank.",
            )

        bank_meta = get_bank_info(cleaned_bic)
        bic_country = cleaned_bic[4:6]
        dest_country = request.recipient_country.upper()

        if bic_country != dest_country:
            return (
                CheckItem(
                    check_id="bic_validation",
                    name="SWIFT/BIC Code Validation",
                    passed=True,
                    severity="WARNING",
                    score_impact=15,
                    message=(
                        f"SWIFT/BIC country code '{bic_country}' differs from recipient destination '{dest_country}' "
                        f"({bank_meta.get('bank_name', 'Unknown Bank')})."
                    ),
                    details={"bic": cleaned_bic, "bank_meta": bank_meta},
                ),
                f"Verify whether {bank_meta.get('bank_name')} in {bic_country} acts as an authorized clearing hub for the beneficiary.",
            )

        return (
            CheckItem(
                check_id="bic_validation",
                name="SWIFT/BIC Code Validation",
                passed=True,
                severity="INFO",
                score_impact=0,
                message=f"{reason} Resolved to {bank_meta.get('bank_name', 'Registered Institution')}.",
                details={"bic": cleaned_bic, "bank_meta": bank_meta},
            ),
            None,
        )

    def _check_currency_code(self, request: PaymentValidationRequest) -> Tuple[CheckItem, Optional[str]]:
        """Check c: Validate ISO 4217 currency code."""
        curr = (request.currency or "").strip().upper()
        is_valid, reason = validate_currency(curr)

        if not is_valid:
            return (
                CheckItem(
                    check_id="currency_code_validation",
                    name="ISO 4217 Currency Code",
                    passed=False,
                    severity="ERROR",
                    score_impact=50,
                    message=reason,
                    details={"currency": curr, "is_valid": False},
                ),
                f"Replace '{curr}' with a standard, active 3-letter ISO 4217 currency code.",
            )

        info = get_currency_info(curr)
        return (
            CheckItem(
                check_id="currency_code_validation",
                name="ISO 4217 Currency Code",
                passed=True,
                severity="INFO",
                score_impact=0,
                message=reason,
                details={"currency": curr, "name": info.get("name")},
            ),
            None,
        )

    def _check_currency_country_compat(self, request: PaymentValidationRequest) -> Tuple[CheckItem, Optional[str]]:
        """Check d: Verify compatibility between selected currency and recipient country."""
        curr = request.currency.strip().upper()
        dest_country = request.recipient_country.strip().upper()

        info = get_currency_info(curr)
        if not info:
            return (
                CheckItem(
                    check_id="currency_country_compatibility",
                    name="Currency-Country Compatibility",
                    passed=False,
                    severity="ERROR",
                    score_impact=30,
                    message=f"Cannot assess compatibility for unrecognized currency '{curr}'.",
                ),
                "Use an active ISO 4217 currency code.",
            )

        native_countries = set(info.get("countries", []))

        # Check 1: Currency is official native currency of destination country
        if dest_country in native_countries:
            return (
                CheckItem(
                    check_id="currency_country_compatibility",
                    name="Currency-Country Compatibility",
                    passed=True,
                    severity="INFO",
                    score_impact=0,
                    message=f"Currency {curr} is the native official legal tender in {dest_country}.",
                    details={"currency": curr, "destination": dest_country, "is_native": True},
                ),
                None,
            )

        # Check 2: Currency is a recognized international settlement currency
        if curr in GLOBAL_SETTLEMENT_CURRENCIES:
            return (
                CheckItem(
                    check_id="currency_country_compatibility",
                    name="Currency-Country Compatibility",
                    passed=True,
                    severity="INFO",
                    score_impact=5,
                    message=(
                        f"{curr} is not the local legal tender of {dest_country}. Some providers or "
                        "beneficiary banks may support this settlement currency; acceptance is not verified here."
                    ),
                    details={
                        "currency": curr,
                        "destination": dest_country,
                        "is_global_settlement_currency": True,
                        "acceptance_verified": False,
                    },
                ),
                f"Verify that recipient's bank account in {dest_country} accepts {curr} or supports multi-currency auto-conversion.",
            )

        # Check 3: Non-reserve foreign currency sent to destination country (e.g. BRL to DE, or JPY to NG)
        return (
            CheckItem(
                check_id="currency_country_compatibility",
                name="Currency-Country Compatibility",
                passed=False,
                severity="WARNING",
                score_impact=25,
                message=(
                    f"Incompatibility risk: {curr} is not commonly cleared in {dest_country}. "
                    f"Non-reserve currency transfers into foreign domestic accounts often fail or get returned."
                ),
                details={"currency": curr, "destination": dest_country, "native_countries": list(native_countries)},
            ),
            f"Convert transfer to {dest_country}'s native currency or a major settlement currency (USD/EUR) prior to dispatch.",
        )

    def _check_amount(self, request: PaymentValidationRequest) -> Tuple[CheckItem, Optional[str]]:
        """Check e: Verify amount positivity and decimal place precision against ISO 4217 minor units."""
        amt = request.amount
        curr = request.currency.strip().upper()

        if amt <= 0:
            return (
                CheckItem(
                    check_id="amount_validation",
                    name="Payment Amount Precision",
                    passed=False,
                    severity="ERROR",
                    score_impact=50,
                    message=f"Invalid payment amount {amt}. Amount must be strictly greater than zero.",
                    details={"amount": amt},
                ),
                "Enter a positive payment amount.",
            )

        curr_info = get_currency_info(curr)
        minor_units = curr_info.get("minor_units", 2)

        # Determine decimal places of given amount
        str_val = f"{amt:.10f}".rstrip("0")
        if "." in str_val:
            decimals_count = len(str_val.split(".")[1])
        else:
            decimals_count = 0

        if decimals_count > minor_units:
            return (
                CheckItem(
                    check_id="amount_validation",
                    name="Payment Amount Precision",
                    passed=False,
                    severity="ERROR",
                    score_impact=35,
                    message=(
                        f"Amount {amt} has {decimals_count} decimal places, but currency {curr} "
                        f"supports a maximum of {minor_units} minor units."
                    ),
                    details={"amount": amt, "decimals": decimals_count, "max_allowed": minor_units},
                ),
                f"Round payment amount to {minor_units} decimal places for {curr}.",
            )

        if amt > 5_000_000.0:
            return (
                CheckItem(
                    check_id="amount_validation",
                    name="Payment Amount Precision",
                    passed=True,
                    severity="WARNING",
                    score_impact=15,
                    message=(
                        f"High-value threshold alert: Payment of {amt:,.2f} {curr} exceeds standard automated thresholds "
                        f"and may trigger central bank large-value reporting."
                    ),
                    details={"amount": amt, "high_value": True},
                ),
                "Ensure compliance documentation and dual-approval authorizations are secured for this high-value transfer.",
            )

        return (
            CheckItem(
                check_id="amount_validation",
                name="Payment Amount Precision",
                passed=True,
                severity="INFO",
                score_impact=0,
                message=f"Amount {amt:,.2f} {curr} is valid with appropriate minor units ({minor_units}).",
                details={"amount": amt, "minor_units": minor_units},
            ),
            None,
        )

    def _check_corridor(self, request: PaymentValidationRequest) -> Tuple[CheckItem, Optional[str]]:
        """Check f: Assess payment corridor risk from sender_country to recipient_country."""
        corridor = get_corridor_risk(request.sender_country, request.recipient_country)
        risk_level = corridor["risk_level"]
        impact = corridor["risk_score_impact"]
        reasons = corridor["typical_failure_reasons"]
        notes = corridor["compliance_notes"]

        if corridor.get("is_sanctioned_or_restricted", False):
            return (
                CheckItem(
                    check_id="corridor_risk_assessment",
                    name="Corridor Risk Assessment",
                    passed=True,
                    severity="WARNING",
                    score_impact=40,
                    message=(
                        f"Static corridor data flags {corridor['corridor']} for enhanced review. This offline dataset "
                        "may be incomplete or outdated and does not determine legal permissibility."
                    ),
                    details={**corridor, "authoritative_screening": False},
                ),
                "Pause for jurisdiction-specific compliance review using current authoritative sources before any payment decision.",
            )

        if risk_level == "HIGH":
            fail_pct = round(corridor["estimated_failure_rate"] * 100, 1)
            primary_reason = reasons[0] if reasons else "High failure corridor"
            return (
                CheckItem(
                    check_id="corridor_risk_assessment",
                    name="Corridor Risk Assessment",
                    passed=True,
                    severity="WARNING",
                    score_impact=impact,
                    message=(
                        f"High risk corridor {corridor['corridor']} with estimated {fail_pct}% failure rate. "
                        f"Primary bottleneck: {primary_reason}."
                    ),
                    details=corridor,
                ),
                f"Mitigate corridor risk: {notes[0] if notes else 'Attach detailed invoice and recipient identification.'}",
            )

        if risk_level == "MEDIUM":
            fail_pct = round(corridor["estimated_failure_rate"] * 100, 1)
            primary_reason = reasons[0] if reasons else "Intermediary routing required"
            return (
                CheckItem(
                    check_id="corridor_risk_assessment",
                    name="Corridor Risk Assessment",
                    passed=True,
                    severity="WARNING",
                    score_impact=impact,
                    message=(
                        f"Moderate risk corridor {corridor['corridor']} with estimated {fail_pct}% failure rate. "
                        f"Watch for: {primary_reason}."
                    ),
                    details=corridor,
                ),
                f"Corridor guidance: {notes[0] if notes else 'Ensure recipient tax identifier is populated.'}",
            )

        return (
            CheckItem(
                check_id="corridor_risk_assessment",
                name="Corridor Risk Assessment",
                passed=True,
                severity="INFO",
                score_impact=0,
                message=f"Low risk corridor {corridor['corridor']} with established bilateral clearing rails.",
                details=corridor,
            ),
            None,
        )

    def _check_timing(
        self,
        request: PaymentValidationRequest,
        now_utc: datetime,
    ) -> Tuple[CheckItem, Optional[str]]:
        """Check g: Check destination RTGS operating hours and banking days."""
        timing = get_optimal_send_time(request.recipient_country, now_utc)
        penalty = timing["timing_penalty"]
        advice = timing["timing_advice"]

        if penalty > 0:
            return (
                CheckItem(
                    check_id="timing_optimization",
                    name="Clearing Schedule and Timing",
                    passed=True,
                    severity="WARNING",
                    score_impact=penalty,
                    message=f"Suboptimal dispatch time: {advice}",
                    details=timing,
                ),
                f"Schedule dispatch during destination active RTGS window ({timing['recommended_window']}) for immediate clearance.",
            )

        return (
            CheckItem(
                check_id="timing_optimization",
                name="Clearing Schedule and Timing",
                passed=True,
                severity="INFO",
                score_impact=0,
                message=f"Optimal execution timing: {timing['rtgs_system']} is currently OPEN in {request.recipient_country}.",
                details=timing,
            ),
            None,
        )

    def _check_duplicate(
        self,
        request: PaymentValidationRequest,
        db: Optional[Session],
        now_utc: datetime,
    ) -> Tuple[CheckItem, Optional[str]]:
        """Check h: Detect duplicate payments submitted within a 24-hour window."""
        if db is None:
            return (
                CheckItem(
                    check_id="duplicate_detection",
                    name="Duplicate Payment Detection",
                    passed=False,
                    severity="WARNING",
                    score_impact=30,
                    message="Duplicate check is unavailable; manual review is required before proceeding.",
                    details={"db_connected": False},
                ),
                "Repeat this validation with database access or verify the payment manually before proceeding.",
            )

        since_time = now_utc - timedelta(hours=24)
        req_ref = request.reference.strip().lower()
        req_name = request.recipient_name.strip().lower()
        req_iban = format_iban(request.iban) if request.iban else None

        query = db.query(ValidationLog).filter(
            ValidationLog.created_at >= since_time,
            ValidationLog.amount == request.amount,
            ValidationLog.currency == request.currency.upper(),
            func.lower(func.trim(ValidationLog.reference)) == req_ref,
            or_(
                func.lower(func.trim(ValidationLog.recipient_name)) == req_name,
                ValidationLog.iban == req_iban if req_iban else False,
            ),
        )
        matched_record = query.order_by(ValidationLog.created_at.desc()).first()

        if matched_record:
            time_diff = now_utc - matched_record.created_at.replace(tzinfo=timezone.utc)
            minutes_ago = max(1, int(time_diff.total_seconds() // 60))
            return (
                CheckItem(
                    check_id="duplicate_detection",
                    name="Duplicate Payment Detection",
                    passed=False,
                    severity="ERROR",
                    score_impact=50,
                    message=(
                        f"Potential duplicate payment detected! Identical payment of {request.amount} {request.currency} "
                        f"to '{request.recipient_name}' with reference '{request.reference}' was submitted {minutes_ago} minutes ago "
                        f"(Log ID: {matched_record.id})."
                    ),
                    details={
                        "duplicate_id": matched_record.id,
                        "submitted_at": matched_record.created_at.isoformat(),
                        "minutes_ago": minutes_ago,
                    },
                ),
                "Verify whether this is an intentional recurring payment or accidental duplicate entry. Update reference if intentional.",
            )

        return (
            CheckItem(
                check_id="duplicate_detection",
                name="Duplicate Payment Detection",
                passed=True,
                severity="INFO",
                score_impact=0,
                message="No duplicate payments detected within the last 24 hours.",
                details={"window_hours": 24},
            ),
            None,
        )

    def _check_sanctions(self, request: PaymentValidationRequest) -> Tuple[CheckItem, Optional[str]]:
        """Check i: Pre-screen narrative and party names for sanctions and sensitive keywords."""
        text_corpus = f"{request.recipient_name} {request.reference}".lower()

        # Check known commercial false positives first
        for phrase, description in SANCTIONS_FALSE_POSITIVES.items():
            if phrase in text_corpus:
                return (
                    CheckItem(
                        check_id="sanctions_keyword_prescreen",
                        name="Sanctions Keyword Pre-Screen",
                        passed=True,
                        severity="WARNING",
                        score_impact=15,
                        message=(
                            f"Payment text contains the phrase '{phrase}' ({description}). This heuristic can produce "
                            "false positives and is not an authoritative sanctions determination."
                        ),
                        details={
                            "flagged_term": phrase,
                            "is_known_false_positive": True,
                            "authoritative_screening": False,
                        },
                    ),
                    "Review the match in context using an authorized compliance screening process; do not alter payment details to evade screening.",
                )

        # Check strictly prohibited terms
        for term in PROHIBITED_SANCTIONS_TERMS:
            # Word boundary search to avoid accidental partial matches (e.g. 'iran' in 'miranda')
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, text_corpus):
                return (
                    CheckItem(
                        check_id="sanctions_keyword_prescreen",
                        name="Sanctions Keyword Pre-Screen",
                        passed=False,
                        severity="WARNING",
                        score_impact=30,
                        message=(
                            f"Sanctions keyword pre-screen found '{term}' in the supplied text. This is not an "
                            "authoritative list match; manual review with an approved screening provider is required."
                        ),
                        details={
                            "flagged_term": term,
                            "authoritative_screening": False,
                            "manual_review_required": True,
                        },
                    ),
                    "Do not treat this keyword match as a sanctions determination. Refer the payment for review using an authorized screening process.",
                )

        return (
            CheckItem(
                check_id="sanctions_keyword_prescreen",
                name="Sanctions Keyword Pre-Screen",
                passed=True,
                severity="INFO",
                score_impact=0,
                message=(
                    "No configured keywords were found. This local pre-screen is not authoritative sanctions screening "
                    "and cannot establish that a party is not sanctioned."
                ),
                details={"prescreen_passed": True, "authoritative_screening": False},
            ),
            None,
        )

    def _check_reference(self, request: PaymentValidationRequest) -> Tuple[CheckItem, Optional[str]]:
        """Check j: Validate payment reference length and SWIFT X-character set compliance."""
        ref = request.reference or ""
        cleaned_ref = ref.strip()

        if not cleaned_ref:
            return (
                CheckItem(
                    check_id="reference_format_check",
                    name="Reference Format and Character Set",
                    passed=True,
                    severity="WARNING",
                    score_impact=15,
                    message="Payment reference is empty. Transactions lacking reference information experience delayed reconciliation.",
                    details={"length": 0},
                ),
                "Add an invoice or remittance reference to expedite beneficiary account reconciliation.",
            )

        if len(cleaned_ref) > 140:
            return (
                CheckItem(
                    check_id="reference_format_check",
                    name="Reference Format and Character Set",
                    passed=True,
                    severity="WARNING",
                    score_impact=10,
                    message=(
                        f"Reference length ({len(cleaned_ref)} chars) exceeds standard SWIFT MT103 Field 70 limit of 140 characters. "
                        f"Intermediary networks will truncate the trailing text."
                    ),
                    details={"length": len(cleaned_ref), "max_allowed": 140},
                ),
                "Shorten payment reference to 140 characters or fewer to prevent truncated invoice numbers.",
            )

        # Check for characters outside SWIFT X-Character set
        if not SWIFT_X_ALLOWED_REGEX.match(cleaned_ref):
            illegal_chars = set(c for c in cleaned_ref if not re.match(r"[A-Za-z0-9/\-?:().,'+ ]", c))
            illegal_str = "".join(sorted(illegal_chars))
            return (
                CheckItem(
                    check_id="reference_format_check",
                    name="Reference Format and Character Set",
                    passed=True,
                    severity="WARNING",
                    score_impact=12,
                    message=(
                        f"Reference contains non-standard characters '{illegal_str}' outside the SWIFT X-character set. "
                        f"These characters cause XML validation errors or silent stripping in clearing gateways."
                    ),
                    details={"illegal_characters": list(illegal_chars)},
                ),
                f"Remove non-SWIFT characters '{illegal_str}' from reference. Use only alphanumeric characters, spaces, and standard delimiters (/ - : . , +).",
            )

        return (
            CheckItem(
                check_id="reference_format_check",
                name="Reference Format and Character Set",
                passed=True,
                severity="INFO",
                score_impact=0,
                message=f"Reference format is compliant with SWIFT MT103 and ISO 20022 character set standards ({len(cleaned_ref)} chars).",
                details={"length": len(cleaned_ref)},
            ),
            None,
        )
