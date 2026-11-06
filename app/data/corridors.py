"""
Cross-border payment corridor risk analysis and timing optimization.

Provides empirical risk levels, failure rate estimates, common rejection reasons,
and optimal execution windows based on RTGS clearing schedules.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import zoneinfo

# European Union member states participating in SEPA / TARGET2
EU_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE"
}

# Sanctioned or high-risk jurisdictions under comprehensive international restrictions
RESTRICTED_COUNTRIES = {
    "CU",  # Cuba
    "IR",  # Iran
    "KP",  # North Korea
    "SY",  # Syria
    "RU",  # Russia (Extensive sanctions)
    "BY",  # Belarus (Extensive sanctions)
    "MM",  # Myanmar / Burma (FATF Blacklist)
    "VE",  # Venezuela (Designated entities)
}

# Specific corridor risk profiles
SPECIFIC_CORRIDORS: Dict[str, Dict[str, Any]] = {
    "US-UK": {
        "risk_level": "LOW",
        "estimated_failure_rate": 0.012,
        "risk_score_impact": 0,
        "typical_failure_reasons": [
            "Missing or incorrect Sort Code/Account number pairing",
            "Transposed digits in UK sort code",
            "Weekend settlement backlog at recipient clearing bank",
        ],
        "compliance_notes": ["Direct settlement via CHAPS/FPS correspondent networks."],
    },
    "US-CA": {
        "risk_level": "LOW",
        "estimated_failure_rate": 0.011,
        "risk_score_impact": 0,
        "typical_failure_reasons": [
            "Missing Canadian transit number or 3-digit financial institution number",
            "Currency mismatch between USD account and CAD account",
        ],
        "compliance_notes": ["Direct Lynx/ACSS cross-border clearing rails."],
    },
    "US-AU": {
        "risk_level": "LOW",
        "estimated_failure_rate": 0.014,
        "risk_score_impact": 0,
        "typical_failure_reasons": [
            "Invalid 6-digit BSB (Bank State Branch) code",
            "Cross-day cutoff timing delays over international date line",
        ],
        "compliance_notes": ["Direct RBA RITS settlement."],
    },
    "UK-EU": {
        "risk_level": "LOW",
        "estimated_failure_rate": 0.013,
        "risk_score_impact": 0,
        "typical_failure_reasons": [
            "SEPA post-Brexit originator address requirement missing",
            "Intermediary EUR-GBP conversion discrepancies",
        ],
        "compliance_notes": ["Post-Brexit SEPA transactions require full debtor physical address."],
    },
    "US-BR": {
        "risk_level": "MEDIUM",
        "estimated_failure_rate": 0.052,
        "risk_score_impact": 20,
        "typical_failure_reasons": [
            "Missing beneficiary CPF (individual) or CNPJ (corporate) tax ID",
            "Unregistered foreign exchange contract with Banco Central do Brasil",
            "Beneficiary name does not match exact tax registry records",
        ],
        "compliance_notes": [
            "Brazilian regulations require valid CPF/CNPJ in payment narrative or reference.",
        ],
    },
    "US-MX": {
        "risk_level": "MEDIUM",
        "estimated_failure_rate": 0.048,
        "risk_score_impact": 18,
        "typical_failure_reasons": [
            "Invalid 18-digit CLABE number checksum",
            "Missing RFC (tax registry) identifier for corporate recipients",
            "SPEI real-time clearing rejection due to beneficiary name mismatch",
        ],
        "compliance_notes": ["Validate 18-digit CLABE format before dispatch to avoid SPEI return fees."],
    },
    "UK-IN": {
        "risk_level": "MEDIUM",
        "estimated_failure_rate": 0.045,
        "risk_score_impact": 18,
        "typical_failure_reasons": [
            "Missing mandatory RBI (Reserve Bank of India) Purpose Code (e.g. P0802 for software)",
            "Incorrect 11-character IFSC code for destination branch",
            "FIRC (Foreign Inward Remittance Certificate) compliance hold",
        ],
        "compliance_notes": [
            "Reserve Bank of India requires mandatory Purpose Code in remittance information.",
        ],
    },
    "EU-TR": {
        "risk_level": "MEDIUM",
        "estimated_failure_rate": 0.061,
        "risk_score_impact": 22,
        "typical_failure_reasons": [
            "CBRT foreign exchange documentation missing for commercial invoices",
            "Turkish IBAN prefix missing or improperly formatted",
            "Tax identification number omitted for Turkish beneficiary",
        ],
        "compliance_notes": ["Turkish Central Bank (CBRT) monitors cross-border trade settlements."],
    },
    "US-JP": {
        "risk_level": "MEDIUM",
        "estimated_failure_rate": 0.034,
        "risk_score_impact": 15,
        "typical_failure_reasons": [
            "Beneficiary name mismatch with Zengin network Katakana records",
            "Missing 4-digit bank code or 3-digit branch code",
            "Foreign exchange reporting threshold exceeded without BoJ filing",
        ],
        "compliance_notes": ["Japanese banks require exact match with Katakana account registration."],
    },
    "US-NG": {
        "risk_level": "HIGH",
        "estimated_failure_rate": 0.124,
        "risk_score_impact": 35,
        "typical_failure_reasons": [
            "Central Bank of Nigeria (CBN) foreign exchange liquidity constraints",
            "Missing Form A or Form M trade clearance reference",
            "Intermediary correspondent bank clearance hold or de-risking rejection",
            "Strict beneficiary Bank Verification Number (BVN) mismatch",
        ],
        "compliance_notes": [
            "High scrutiny corridor: Ensure complete invoice documentation and official CBN purpose.",
        ],
    },
    "EU-PH": {
        "risk_level": "HIGH",
        "estimated_failure_rate": 0.098,
        "risk_score_impact": 30,
        "typical_failure_reasons": [
            "Anti-Money Laundering Council (AMLC) enhanced due diligence flag",
            "PhilPaSS clearing cut-off missed by local receiving institution",
            "Incomplete beneficiary residential address triggering correspondent hold",
        ],
        "compliance_notes": ["Provide full debtor and creditor physical addresses to avoid AMLC holds."],
    },
    "US-VN": {
        "risk_level": "HIGH",
        "estimated_failure_rate": 0.112,
        "risk_score_impact": 35,
        "typical_failure_reasons": [
            "State Bank of Vietnam strict capital control compliance rejection",
            "Missing underlying commercial contracts or service invoices",
            "Inability of recipient to verify purpose of inward remittance",
        ],
        "compliance_notes": [
            "Commercial payments to Vietnam require supporting documentation prior to release.",
        ],
    },
    "UK-KE": {
        "risk_level": "HIGH",
        "estimated_failure_rate": 0.105,
        "risk_score_impact": 32,
        "typical_failure_reasons": [
            "Central Bank of Kenya (CBK) foreign exchange transaction declaration hold",
            "Mobile money / KEPSS RTGS bridge timeout or account limit exceeded",
            "Missing beneficiary national ID or KRA PIN",
        ],
        "compliance_notes": ["Verify KRA PIN and transaction purpose before dispatch."],
    },
    "US-EG": {
        "risk_level": "HIGH",
        "estimated_failure_rate": 0.091,
        "risk_score_impact": 30,
        "typical_failure_reasons": [
            "Central Bank of Egypt foreign currency allocation queue delays",
            "Strict documentary collection / letter of credit compliance requirements",
            "Correspondent bank processing delays and requests for information (RFI)",
        ],
        "compliance_notes": ["Subject to CBE foreign currency regulations and clearing queues."],
    },
}

# Country specific clearing schedule metadata
COUNTRY_TIME_METADATA: Dict[str, Dict[str, Any]] = {
    "US": {
        "timezone": "America/New_York",
        "business_hours": {"start": "09:00", "end": "17:00", "days": "Monday-Friday"},
        "rtgs_system": "Fedwire / CHIPS",
        "rtgs_hours": {"start": "09:00", "end": "18:30"},
        "recommended_window": "Monday to Friday 09:30-15:00 EST",
    },
    "GB": {
        "timezone": "Europe/London",
        "business_hours": {"start": "09:00", "end": "17:00", "days": "Monday-Friday"},
        "rtgs_system": "CHAPS / Faster Payments",
        "rtgs_hours": {"start": "06:00", "end": "18:00"},
        "recommended_window": "Monday to Friday 09:00-15:30 GMT/BST",
    },
    "DE": {
        "timezone": "Europe/Berlin",
        "business_hours": {"start": "08:30", "end": "17:00", "days": "Monday-Friday"},
        "rtgs_system": "TARGET2 / SEPA Instant",
        "rtgs_hours": {"start": "07:00", "end": "18:00"},
        "recommended_window": "Monday to Friday 08:30-15:00 CET",
    },
    "FR": {
        "timezone": "Europe/Paris",
        "business_hours": {"start": "09:00", "end": "17:30", "days": "Monday-Friday"},
        "rtgs_system": "TARGET2",
        "rtgs_hours": {"start": "07:00", "end": "18:00"},
        "recommended_window": "Monday to Friday 09:00-15:00 CET",
    },
    "JP": {
        "timezone": "Asia/Tokyo",
        "business_hours": {"start": "09:00", "end": "15:00", "days": "Monday-Friday"},
        "rtgs_system": "BOJ-NET / Zengin",
        "rtgs_hours": {"start": "08:30", "end": "15:30"},
        "recommended_window": "Monday to Thursday 09:00-13:00 JST",
    },
    "SG": {
        "timezone": "Asia/Singapore",
        "business_hours": {"start": "09:00", "end": "17:00", "days": "Monday-Friday"},
        "rtgs_system": "MEPS+",
        "rtgs_hours": {"start": "09:00", "end": "16:30"},
        "recommended_window": "Monday to Friday 09:30-14:30 SGT",
    },
    "AU": {
        "timezone": "Australia/Sydney",
        "business_hours": {"start": "09:00", "end": "17:00", "days": "Monday-Friday"},
        "rtgs_system": "RBA RITS / NPP",
        "rtgs_hours": {"start": "07:30", "end": "18:30"},
        "recommended_window": "Monday to Friday 09:00-15:00 AEST/AEDT",
    },
    "CA": {
        "timezone": "America/Toronto",
        "business_hours": {"start": "09:00", "end": "17:00", "days": "Monday-Friday"},
        "rtgs_system": "Lynx (Large Value)",
        "rtgs_hours": {"start": "07:00", "end": "18:00"},
        "recommended_window": "Monday to Friday 09:00-16:00 EST",
    },
    "IN": {
        "timezone": "Asia/Kolkata",
        "business_hours": {"start": "09:30", "end": "17:30", "days": "Monday-Friday"},
        "rtgs_system": "RBI RTGS / NEFT",
        "rtgs_hours": {"start": "00:00", "end": "24:00"},  # 24x7 RTGS
        "recommended_window": "Monday to Friday 10:00-16:00 IST (for bank desk clearance)",
    },
    "BR": {
        "timezone": "America/Sao_Paulo",
        "business_hours": {"start": "10:00", "end": "16:00", "days": "Monday-Friday"},
        "rtgs_system": "STR / PIX",
        "rtgs_hours": {"start": "06:30", "end": "18:30"},
        "recommended_window": "Monday to Thursday 10:00-14:00 BRT",
    },
    "MX": {
        "timezone": "America/Mexico_City",
        "business_hours": {"start": "09:00", "end": "16:00", "days": "Monday-Friday"},
        "rtgs_system": "SPEI / SPID",
        "rtgs_hours": {"start": "07:00", "end": "17:30"},
        "recommended_window": "Monday to Friday 09:30-14:30 CST",
    },
    "NG": {
        "timezone": "Africa/Lagos",
        "business_hours": {"start": "08:00", "end": "16:00", "days": "Monday-Friday"},
        "rtgs_system": "CBN CIFTS / NIBSS",
        "rtgs_hours": {"start": "08:30", "end": "15:00"},
        "recommended_window": "Tuesday to Thursday 09:00-13:00 WAT",
    },
    "KE": {
        "timezone": "Africa/Nairobi",
        "business_hours": {"start": "08:30", "end": "16:30", "days": "Monday-Friday"},
        "rtgs_system": "KEPSS RTGS",
        "rtgs_hours": {"start": "08:30", "end": "15:30"},
        "recommended_window": "Monday to Thursday 09:00-14:00 EAT",
    },
    "EG": {
        "timezone": "Africa/Cairo",
        "business_hours": {"start": "08:30", "end": "15:30", "days": "Sunday-Thursday"},
        "rtgs_system": "CBE RTGS",
        "rtgs_hours": {"start": "08:30", "end": "14:30"},
        "recommended_window": "Sunday to Wednesday 09:00-13:00 EET",
    },
    "SA": {
        "timezone": "Asia/Riyadh",
        "business_hours": {"start": "09:00", "end": "17:00", "days": "Sunday-Thursday"},
        "rtgs_system": "SARIE",
        "rtgs_hours": {"start": "08:00", "end": "15:30"},
        "recommended_window": "Sunday to Wednesday 09:30-14:00 AST",
    },
    "AE": {
        "timezone": "Asia/Dubai",
        "business_hours": {"start": "08:00", "end": "16:00", "days": "Monday-Friday"},
        "rtgs_system": "UAEFTS",
        "rtgs_hours": {"start": "08:00", "end": "16:00"},
        "recommended_window": "Monday to Thursday 09:00-14:00 GST",
    },
    "CH": {
        "timezone": "Europe/Zurich",
        "business_hours": {"start": "08:30", "end": "17:00", "days": "Monday-Friday"},
        "rtgs_system": "SIC (Swiss Interbank Clearing)",
        "rtgs_hours": {"start": "07:00", "end": "18:15"},
        "recommended_window": "Monday to Friday 09:00-15:00 CET",
    },
}


def get_corridor_risk(from_country: str, to_country: str) -> Dict[str, Any]:
    """
    Assess payment corridor risk, estimated failure rate, and common failure causes.

    Args:
        from_country: ISO 3166-1 alpha-2 origin country code.
        to_country: ISO 3166-1 alpha-2 destination country code.

    Returns:
        Dictionary containing risk level, failure rate, score penalty, and operational notes.
    """
    src = (from_country or "").strip().upper()
    dst = (to_country or "").strip().upper()
    corridor_key = f"{src}-{dst}"

    # Check sanctioned or restricted countries first
    if src in RESTRICTED_COUNTRIES or dst in RESTRICTED_COUNTRIES:
        restricted_name = dst if dst in RESTRICTED_COUNTRIES else src
        return {
            "corridor": corridor_key,
            "from_country": src,
            "to_country": dst,
            "risk_level": "VERY_HIGH",
            "estimated_failure_rate": 0.999,
            "risk_score_impact": 85,
            "is_sanctioned_or_restricted": True,
            "typical_failure_reasons": [
                f"Country {restricted_name} is under international sanctions or severe AML embargo",
                "Transaction will be blocked by intermediary clearing banks",
                "Asset freeze regulations prohibit processing cross-border payments",
            ],
            "compliance_notes": [
                "CRITICAL: Transaction prohibited under international sanctions and AML compliance mandates."
            ],
        }

    # Direct match in specific corridors table
    if corridor_key in SPECIFIC_CORRIDORS:
        item = SPECIFIC_CORRIDORS[corridor_key]
        return {
            "corridor": corridor_key,
            "from_country": src,
            "to_country": dst,
            "risk_level": item["risk_level"],
            "estimated_failure_rate": item["estimated_failure_rate"],
            "risk_score_impact": item["risk_score_impact"],
            "is_sanctioned_or_restricted": False,
            "typical_failure_reasons": list(item["typical_failure_reasons"]),
            "compliance_notes": list(item["compliance_notes"]),
        }

    # Generalized EU-EU corridor
    if src in EU_COUNTRIES and dst in EU_COUNTRIES:
        return {
            "corridor": corridor_key,
            "from_country": src,
            "to_country": dst,
            "risk_level": "LOW",
            "estimated_failure_rate": 0.008,
            "risk_score_impact": 0,
            "is_sanctioned_or_restricted": False,
            "typical_failure_reasons": [
                "Incorrect IBAN checksum",
                "Beneficiary account closed or dormant",
            ],
            "compliance_notes": [
                "Intra-EU SEPA zone transaction: Low clearing risk and same-day/instant settlement capability."
            ],
        }

    # US to EU or EU to US
    if (src == "US" and dst in EU_COUNTRIES) or (src in EU_COUNTRIES and dst == "US"):
        return {
            "corridor": corridor_key,
            "from_country": src,
            "to_country": dst,
            "risk_level": "LOW",
            "estimated_failure_rate": 0.015,
            "risk_score_impact": 0,
            "is_sanctioned_or_restricted": False,
            "typical_failure_reasons": [
                "Missing intermediary correspondent routing instructions",
                "Beneficiary address formatting issues",
            ],
            "compliance_notes": ["High-liquidity transatlantic correspondent banking channel."],
        }

    # Major G10 / Low-Risk pairings
    g10_countries = {"US", "GB", "DE", "FR", "JP", "CH", "CA", "AU", "NZ", "SE", "NO", "DK", "SG", "NL", "IE"}
    if src in g10_countries and dst in g10_countries:
        return {
            "corridor": corridor_key,
            "from_country": src,
            "to_country": dst,
            "risk_level": "LOW",
            "estimated_failure_rate": 0.018,
            "risk_score_impact": 0,
            "is_sanctioned_or_restricted": False,
            "typical_failure_reasons": [
                "Beneficiary name formatting mismatch",
                "Cut-off time passed at receiving bank",
            ],
            "compliance_notes": ["Established clearing corridors with mature bilateral SWIFT connectivity."],
        }

    # Standard fallback corridor
    return {
        "corridor": corridor_key,
        "from_country": src,
        "to_country": dst,
        "risk_level": "MEDIUM",
        "estimated_failure_rate": 0.045,
        "risk_score_impact": 15,
        "is_sanctioned_or_restricted": False,
        "typical_failure_reasons": [
            "Intermediary correspondent bank fees deducted from principal",
            "Beneficiary account details require manual verification",
            "National regulatory reporting threshold inquiries",
        ],
        "compliance_notes": [
            "Standard international SWIFT wire transfer. Ensure beneficiary account and BIC are precise."
        ],
    }


def get_optimal_send_time(to_country: str, current_time_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Compute optimal send window, recipient local time, and RTGS clearing availability.

    Args:
        to_country: ISO 3166-1 alpha-2 destination country.
        current_time_utc: Optional UTC datetime for evaluation. Defaults to datetime.now(timezone.utc).

    Returns:
        Dictionary with timezone, business hours, RTGS system, local time, and timing status.
    """
    dst = (to_country or "").strip().upper()
    meta = COUNTRY_TIME_METADATA.get(
        dst,
        {
            "timezone": "UTC",
            "business_hours": {"start": "09:00", "end": "17:00", "days": "Monday-Friday"},
            "rtgs_system": "Standard National RTGS",
            "rtgs_hours": {"start": "09:00", "end": "16:00"},
            "recommended_window": "Monday to Friday 09:00-14:00 local time",
        },
    )

    tz_name = meta["timezone"]
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    if current_time_utc is None:
        current_time_utc = datetime.now(timezone.utc)
    elif current_time_utc.tzinfo is None:
        current_time_utc = current_time_utc.replace(tzinfo=timezone.utc)

    local_dt = current_time_utc.astimezone(tz)
    weekday_idx = local_dt.weekday()  # 0=Monday, 6=Sunday
    local_time_str = local_dt.strftime("%H:%M")

    # Determine working days: Middle East uses Sunday-Thursday, most others Monday-Friday
    is_sunday_thursday = "Sunday" in meta["business_hours"]["days"]
    if is_sunday_thursday:
        is_working_day = weekday_idx in (6, 0, 1, 2, 3)  # Sun, Mon, Tue, Wed, Thu
    else:
        is_working_day = weekday_idx in (0, 1, 2, 3, 4)  # Mon, Tue, Wed, Thu, Fri

    bh_start = meta["business_hours"]["start"]
    bh_end = meta["business_hours"]["end"]
    is_business_hours = is_working_day and (bh_start <= local_time_str <= bh_end)

    rtgs_start = meta["rtgs_hours"]["start"]
    rtgs_end = meta["rtgs_hours"]["end"]
    is_rtgs_open = is_working_day and (rtgs_start <= local_time_str <= rtgs_end)

    advice: List[str] = []
    timing_penalty = 0

    if not is_working_day:
        timing_penalty = 10
        advice.append(
            f"Destination bank in {dst} is closed today (Weekend/Non-banking day). "
            f"Payment will queue until the next clearing cycle."
        )
    elif not is_rtgs_open:
        timing_penalty = 8
        if local_time_str < rtgs_start:
            advice.append(
                f"Destination RTGS ({meta['rtgs_system']}) has not opened yet today (opens at {rtgs_start} local time). "
                f"Payment will queue for opening."
            )
        else:
            advice.append(
                f"Daily clearing window closed for {meta['rtgs_system']} (closed at {rtgs_end} local time). "
                f"Payment will settle next business day."
            )
    else:
        advice.append(
            f"Active clearing window: {meta['rtgs_system']} is currently OPEN in {dst}. Optimal for immediate dispatch."
        )

    return {
        "to_country": dst,
        "timezone": tz_name,
        "current_local_time": local_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "local_hour_minute": local_time_str,
        "is_working_day": is_working_day,
        "is_business_hours": is_business_hours,
        "is_rtgs_open": is_rtgs_open,
        "business_hours": meta["business_hours"],
        "rtgs_system": meta["rtgs_system"],
        "rtgs_hours": meta["rtgs_hours"],
        "recommended_window": meta["recommended_window"],
        "timing_penalty": timing_penalty,
        "timing_advice": " ".join(advice),
    }
