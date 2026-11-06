"""
SWIFT / Business Identifier Code (BIC) registry and validation.

Implements ISO 9362 format validation and sample BIC lookup
for cross-border bank identification.
"""

import re
from typing import Dict, Optional, Tuple, TypedDict

# ISO 3166-1 alpha-2 country codes for validating the 5th and 6th chars of a BIC.
ISO_COUNTRY_CODES = {
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT", "AU", "AW", "AX", "AZ",
    "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS",
    "BT", "BV", "BW", "BY", "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN",
    "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM", "DO", "DZ", "EC", "EE",
    "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF",
    "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM",
    "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT", "JE", "JM",
    "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC",
    "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK",
    "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA",
    "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG",
    "PH", "PK", "PL", "PM", "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW",
    "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS",
    "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO",
    "TR", "TT", "TV", "TW", "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
    "VN", "VU", "WF", "WS", "XK", "YE", "YT", "ZA", "ZM", "ZW"
}


class BankInfo(TypedDict):
    found: bool
    bic: str
    bank_name: str
    country: str
    country_code: str
    city: str
    branch: Optional[str]


# Sample valid BICs registry (at least 28 international institutions across continents)
KNOWN_BICS: Dict[str, Dict[str, str]] = {
    "DEUTDEFF": {
        "bank_name": "Deutsche Bank AG",
        "country": "Germany",
        "country_code": "DE",
        "city": "Frankfurt am Main",
        "branch": "Head Office",
    },
    "BARCGB22": {
        "bank_name": "Barclays Bank PLC",
        "country": "United Kingdom",
        "country_code": "GB",
        "city": "London",
        "branch": "Head Office",
    },
    "BNPAFRPP": {
        "bank_name": "BNP Paribas",
        "country": "France",
        "country_code": "FR",
        "city": "Paris",
        "branch": "Head Office",
    },
    "CHASUS33": {
        "bank_name": "JPMorgan Chase Bank, N.A.",
        "country": "United States",
        "country_code": "US",
        "city": "New York",
        "branch": "Head Office",
    },
    "CITIUS33": {
        "bank_name": "Citibank, N.A.",
        "country": "United States",
        "country_code": "US",
        "city": "New York",
        "branch": "Head Office",
    },
    "HSBCGB2L": {
        "bank_name": "HSBC Bank plc",
        "country": "United Kingdom",
        "country_code": "GB",
        "city": "London",
        "branch": "Head Office",
    },
    "SANYESMM": {
        "bank_name": "Banco Santander S.A.",
        "country": "Spain",
        "country_code": "ES",
        "city": "Madrid",
        "branch": "Head Office",
    },
    "UNCRITM1": {
        "bank_name": "UniCredit S.p.A.",
        "country": "Italy",
        "country_code": "IT",
        "city": "Milan",
        "branch": "Head Office",
    },
    "INGBNL2A": {
        "bank_name": "ING Bank N.V.",
        "country": "Netherlands",
        "country_code": "NL",
        "city": "Amsterdam",
        "branch": "Head Office",
    },
    "KREDCHZZ": {
        "bank_name": "Credit Suisse (UBS Group)",
        "country": "Switzerland",
        "country_code": "CH",
        "city": "Zurich",
        "branch": "Head Office",
    },
    "UBSWCHZH": {
        "bank_name": "UBS Switzerland AG",
        "country": "Switzerland",
        "country_code": "CH",
        "city": "Zurich",
        "branch": "Head Office",
    },
    "SMBCJPJT": {
        "bank_name": "Sumitomo Mitsui Banking Corporation",
        "country": "Japan",
        "country_code": "JP",
        "city": "Tokyo",
        "branch": "Head Office",
    },
    "BOTKJPJT": {
        "bank_name": "MUFG Bank, Ltd.",
        "country": "Japan",
        "country_code": "JP",
        "city": "Tokyo",
        "branch": "Head Office",
    },
    "SBININBB": {
        "bank_name": "State Bank of India",
        "country": "India",
        "country_code": "IN",
        "city": "Mumbai",
        "branch": "Head Office",
    },
    "HDFCINBB": {
        "bank_name": "HDFC Bank Limited",
        "country": "India",
        "country_code": "IN",
        "city": "Mumbai",
        "branch": "Head Office",
    },
    "ICICINBB": {
        "bank_name": "ICICI Bank Limited",
        "country": "India",
        "country_code": "IN",
        "city": "Mumbai",
        "branch": "Head Office",
    },
    "BKCHCNBJ": {
        "bank_name": "Bank of China",
        "country": "China",
        "country_code": "CN",
        "city": "Beijing",
        "branch": "Head Office",
    },
    "DBSSSGSG": {
        "bank_name": "DBS Bank Ltd",
        "country": "Singapore",
        "country_code": "SG",
        "city": "Singapore",
        "branch": "Head Office",
    },
    "ANZBAU3M": {
        "bank_name": "Australia and New Zealand Banking Group",
        "country": "Australia",
        "country_code": "AU",
        "city": "Melbourne",
        "branch": "Head Office",
    },
    "ROYCCAT2": {
        "bank_name": "Royal Bank of Canada",
        "country": "Canada",
        "country_code": "CA",
        "city": "Toronto",
        "branch": "Head Office",
    },
    "BBRTBRSP": {
        "bank_name": "Banco do Brasil S.A.",
        "country": "Brazil",
        "country_code": "BR",
        "city": "Sao Paulo",
        "branch": "Head Office",
    },
    "FIRNZAJJ": {
        "bank_name": "FirstRand Bank Limited",
        "country": "South Africa",
        "country_code": "ZA",
        "city": "Johannesburg",
        "branch": "Head Office",
    },
    "KCBKKENX": {
        "bank_name": "KCB Bank Kenya Limited",
        "country": "Kenya",
        "country_code": "KE",
        "city": "Nairobi",
        "branch": "Head Office",
    },
    "FBNINGLA": {
        "bank_name": "First Bank of Nigeria Limited",
        "country": "Nigeria",
        "country_code": "NG",
        "city": "Lagos",
        "branch": "Head Office",
    },
    "ARBIEGCA": {
        "bank_name": "Arab African International Bank",
        "country": "Egypt",
        "country_code": "EG",
        "city": "Cairo",
        "branch": "Head Office",
    },
    "NBADAEAD": {
        "bank_name": "First Abu Dhabi Bank",
        "country": "United Arab Emirates",
        "country_code": "AE",
        "city": "Abu Dhabi",
        "branch": "Head Office",
    },
    "RJHIISRI": {
        "bank_name": "Al Rajhi Banking and Investment Corp",
        "country": "Saudi Arabia",
        "country_code": "SA",
        "city": "Riyadh",
        "branch": "Head Office",
    },
    "TCZATR2A": {
        "bank_name": "TC Ziraat Bankasi A.S.",
        "country": "Turkey",
        "country_code": "TR",
        "city": "Ankara",
        "branch": "Head Office",
    },
}

# Regex for standard ISO 9362 BIC structure:
# 4 alpha chars (bank), 2 alpha chars (country), 2 alnum chars (location), optional 3 alnum chars (branch)
BIC_REGEX = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def format_bic(bic: str) -> str:
    """
    Format BIC string by stripping whitespace and uppercase conversion.

    Args:
        bic: Raw BIC string.

    Returns:
        Cleaned uppercase BIC string.
    """
    if not bic:
        return ""
    return "".join(bic.split()).upper()


def validate_bic(bic: str) -> Tuple[bool, str]:
    """
    Validate SWIFT/BIC code according to ISO 9362 standards.

    Checks:
    - Length is exactly 8 or 11 characters
    - Bank code (positions 1-4) consists of alphabetic letters
    - Country code (positions 5-6) is a recognized ISO 3166-1 alpha-2 code
    - Location code (positions 7-8) consists of alphanumeric characters
    - Branch code (optional positions 9-11) consists of alphanumeric characters

    Args:
        bic: SWIFT/BIC code string.

    Returns:
        Tuple of (is_valid: bool, reason: str).
    """
    if not bic or not isinstance(bic, str):
        return False, "SWIFT/BIC code is empty or missing. A valid 8 or 11 character BIC is required."

    cleaned = format_bic(bic)
    length = len(cleaned)

    if length not in (8, 11):
        return (
            False,
            f"Invalid SWIFT/BIC length ({length} chars). BIC must be exactly 8 characters (primary office) "
            f"or 11 characters (specific branch). Received '{cleaned}'.",
        )

    bank_code = cleaned[:4]
    country_code = cleaned[4:6]
    location_code = cleaned[6:8]
    branch_code = cleaned[8:] if length == 11 else ""

    if not bank_code.isalpha():
        return (
            False,
            f"Invalid bank code '{bank_code}' in BIC. The first 4 characters must be alphabetic letters.",
        )

    if not country_code.isalpha():
        return (
            False,
            f"Invalid country code '{country_code}' in BIC. Characters 5 and 6 must be alphabetic letters.",
        )

    if country_code not in ISO_COUNTRY_CODES:
        return (
            False,
            f"Country code '{country_code}' in BIC is not a recognized ISO 3166-1 country. "
            f"Verify that characters 5 and 6 accurately reflect the bank location.",
        )

    if not location_code.isalnum():
        return (
            False,
            f"Invalid location code '{location_code}' in BIC. Characters 7 and 8 must be alphanumeric.",
        )

    if length == 11 and not branch_code.isalnum():
        return (
            False,
            f"Invalid branch code '{branch_code}' in BIC. Characters 9-11 must be alphanumeric.",
        )

    if not BIC_REGEX.match(cleaned):
        return False, f"SWIFT/BIC '{cleaned}' does not match standard ISO 9362 format."

    return True, f"SWIFT/BIC format is valid ({length} chars, bank: {bank_code}, country: {country_code})."


def get_bank_info(bic: str) -> Dict[str, Optional[str]]:
    """
    Retrieve bank identity and location metadata for a known SWIFT/BIC code.

    Args:
        bic: SWIFT/BIC code string (8 or 11 characters).

    Returns:
        Dictionary with found status, bank name, country, country code, city, and branch.
    """
    if not bic:
        return {
            "found": False,
            "bic": "",
            "bank_name": "Unknown",
            "country": "Unknown",
            "country_code": "",
            "city": "Unknown",
            "branch": None,
        }

    cleaned = format_bic(bic)
    base_8 = cleaned[:8]
    branch_id = cleaned[8:] if len(cleaned) == 11 else None

    # Check exact match or base 8-character match
    if cleaned in KNOWN_BICS:
        info = KNOWN_BICS[cleaned]
        return {
            "found": True,
            "bic": cleaned,
            "bank_name": info["bank_name"],
            "country": info["country"],
            "country_code": info["country_code"],
            "city": info["city"],
            "branch": info.get("branch", "Head Office"),
        }

    if base_8 in KNOWN_BICS:
        info = KNOWN_BICS[base_8]
        branch_desc = "Primary Office" if (not branch_id or branch_id == "XXX") else f"Branch {branch_id}"
        return {
            "found": True,
            "bic": cleaned,
            "bank_name": info["bank_name"],
            "country": info["country"],
            "country_code": info["country_code"],
            "city": info["city"],
            "branch": branch_desc,
        }

    # If country code is known from BIC structure
    country_iso = cleaned[4:6] if len(cleaned) >= 6 and cleaned[4:6].isalpha() else ""
    return {
        "found": False,
        "bic": cleaned,
        "bank_name": "Unregistered / Routing Bank",
        "country": country_iso,
        "country_code": country_iso,
        "city": "Unspecified",
        "branch": branch_id,
    }
