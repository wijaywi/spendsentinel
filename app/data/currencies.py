"""
ISO 4217 Currency registry and currency pair assessment.

Provides standard definitions for currency codes, minor units (decimal places),
jurisdictions, and foreign exchange spread estimations.
"""

from typing import Any, Dict, List, Optional, Tuple, TypedDict


class CurrencyDetail(TypedDict):
    code: str
    name: str
    numeric_code: str
    minor_units: int
    countries: List[str]


# ISO 4217 active currencies registry
CURRENCIES: Dict[str, CurrencyDetail] = {
    "USD": {
        "code": "USD",
        "name": "United States Dollar",
        "numeric_code": "840",
        "minor_units": 2,
        "countries": ["US", "EC", "SV", "PR", "PA", "ZW"],
    },
    "EUR": {
        "code": "EUR",
        "name": "Euro",
        "numeric_code": "978",
        "minor_units": 2,
        "countries": [
            "DE", "FR", "IT", "ES", "NL", "BE", "AT", "PT", "IE", "FI",
            "GR", "SK", "SI", "LT", "LV", "EE", "CY", "MT", "LU", "HR", "ME", "XK"
        ],
    },
    "GBP": {
        "code": "GBP",
        "name": "Pound Sterling",
        "numeric_code": "826",
        "minor_units": 2,
        "countries": ["GB", "GI", "GG", "JE", "IM"],
    },
    "JPY": {
        "code": "JPY",
        "name": "Japanese Yen",
        "numeric_code": "392",
        "minor_units": 0,
        "countries": ["JP"],
    },
    "CHF": {
        "code": "CHF",
        "name": "Swiss Franc",
        "numeric_code": "756",
        "minor_units": 2,
        "countries": ["CH", "LI"],
    },
    "CAD": {
        "code": "CAD",
        "name": "Canadian Dollar",
        "numeric_code": "124",
        "minor_units": 2,
        "countries": ["CA"],
    },
    "AUD": {
        "code": "AUD",
        "name": "Australian Dollar",
        "numeric_code": "036",
        "minor_units": 2,
        "countries": ["AU", "CX", "CC", "HM", "KI", "NR", "NF", "TV"],
    },
    "NZD": {
        "code": "NZD",
        "name": "New Zealand Dollar",
        "numeric_code": "554",
        "minor_units": 2,
        "countries": ["NZ", "CK", "NU", "PN", "TK"],
    },
    "SEK": {
        "code": "SEK",
        "name": "Swedish Krona",
        "numeric_code": "752",
        "minor_units": 2,
        "countries": ["SE"],
    },
    "NOK": {
        "code": "NOK",
        "name": "Norwegian Krone",
        "numeric_code": "578",
        "minor_units": 2,
        "countries": ["NO", "SJ", "BV"],
    },
    "DKK": {
        "code": "DKK",
        "name": "Danish Krone",
        "numeric_code": "208",
        "minor_units": 2,
        "countries": ["DK", "FO", "GL"],
    },
    "PLN": {
        "code": "PLN",
        "name": "Polish Zloty",
        "numeric_code": "985",
        "minor_units": 2,
        "countries": ["PL"],
    },
    "CZK": {
        "code": "CZK",
        "name": "Czech Koruna",
        "numeric_code": "203",
        "minor_units": 2,
        "countries": ["CZ"],
    },
    "HUF": {
        "code": "HUF",
        "name": "Hungarian Forint",
        "numeric_code": "348",
        "minor_units": 2,
        "countries": ["HU"],
    },
    "RON": {
        "code": "RON",
        "name": "Romanian Leu",
        "numeric_code": "946",
        "minor_units": 2,
        "countries": ["RO"],
    },
    "BGN": {
        "code": "BGN",
        "name": "Bulgarian Lev",
        "numeric_code": "975",
        "minor_units": 2,
        "countries": ["BG"],
    },
    "HRK": {
        "code": "HRK",
        "name": "Croatian Kuna (Historical - Replaced by EUR)",
        "numeric_code": "191",
        "minor_units": 2,
        "countries": [],
    },
    "TRY": {
        "code": "TRY",
        "name": "Turkish Lira",
        "numeric_code": "949",
        "minor_units": 2,
        "countries": ["TR"],
    },
    "BRL": {
        "code": "BRL",
        "name": "Brazilian Real",
        "numeric_code": "986",
        "minor_units": 2,
        "countries": ["BR"],
    },
    "MXN": {
        "code": "MXN",
        "name": "Mexican Peso",
        "numeric_code": "484",
        "minor_units": 2,
        "countries": ["MX"],
    },
    "ARS": {
        "code": "ARS",
        "name": "Argentine Peso",
        "numeric_code": "032",
        "minor_units": 2,
        "countries": ["AR"],
    },
    "CLP": {
        "code": "CLP",
        "name": "Chilean Peso",
        "numeric_code": "152",
        "minor_units": 0,
        "countries": ["CL"],
    },
    "COP": {
        "code": "COP",
        "name": "Colombian Peso",
        "numeric_code": "170",
        "minor_units": 2,
        "countries": ["CO"],
    },
    "PEN": {
        "code": "PEN",
        "name": "Peruvian Sol",
        "numeric_code": "604",
        "minor_units": 2,
        "countries": ["PE"],
    },
    "INR": {
        "code": "INR",
        "name": "Indian Rupee",
        "numeric_code": "356",
        "minor_units": 2,
        "countries": ["IN", "BT"],
    },
    "CNY": {
        "code": "CNY",
        "name": "Chinese Yuan",
        "numeric_code": "156",
        "minor_units": 2,
        "countries": ["CN"],
    },
    "HKD": {
        "code": "HKD",
        "name": "Hong Kong Dollar",
        "numeric_code": "344",
        "minor_units": 2,
        "countries": ["HK"],
    },
    "SGD": {
        "code": "SGD",
        "name": "Singapore Dollar",
        "numeric_code": "702",
        "minor_units": 2,
        "countries": ["SG", "BN"],
    },
    "KRW": {
        "code": "KRW",
        "name": "South Korean Won",
        "numeric_code": "410",
        "minor_units": 0,
        "countries": ["KR"],
    },
    "THB": {
        "code": "THB",
        "name": "Thai Baht",
        "numeric_code": "764",
        "minor_units": 2,
        "countries": ["TH"],
    },
    "MYR": {
        "code": "MYR",
        "name": "Malaysian Ringgit",
        "numeric_code": "458",
        "minor_units": 2,
        "countries": ["MY"],
    },
    "IDR": {
        "code": "IDR",
        "name": "Indonesian Rupiah",
        "numeric_code": "360",
        "minor_units": 2,
        "countries": ["ID"],
    },
    "PHP": {
        "code": "PHP",
        "name": "Philippine Peso",
        "numeric_code": "608",
        "minor_units": 2,
        "countries": ["PH"],
    },
    "VND": {
        "code": "VND",
        "name": "Vietnamese Dong",
        "numeric_code": "704",
        "minor_units": 0,
        "countries": ["VN"],
    },
    "TWD": {
        "code": "TWD",
        "name": "New Taiwan Dollar",
        "numeric_code": "901",
        "minor_units": 2,
        "countries": ["TW"],
    },
    "ZAR": {
        "code": "ZAR",
        "name": "South African Rand",
        "numeric_code": "710",
        "minor_units": 2,
        "countries": ["ZA", "NA", "LS", "SZ"],
    },
    "AED": {
        "code": "AED",
        "name": "United Arab Emirates Dirham",
        "numeric_code": "784",
        "minor_units": 2,
        "countries": ["AE"],
    },
    "SAR": {
        "code": "SAR",
        "name": "Saudi Riyal",
        "numeric_code": "682",
        "minor_units": 2,
        "countries": ["SA"],
    },
    "ILS": {
        "code": "ILS",
        "name": "Israeli New Shekel",
        "numeric_code": "376",
        "minor_units": 2,
        "countries": ["IL", "PS"],
    },
    "EGP": {
        "code": "EGP",
        "name": "Egyptian Pound",
        "numeric_code": "818",
        "minor_units": 2,
        "countries": ["EG", "PS"],
    },
    "NGN": {
        "code": "NGN",
        "name": "Nigerian Naira",
        "numeric_code": "566",
        "minor_units": 2,
        "countries": ["NG"],
    },
    "KES": {
        "code": "KES",
        "name": "Kenyan Shilling",
        "numeric_code": "404",
        "minor_units": 2,
        "countries": ["KE"],
    },
    "KWD": {
        "code": "KWD",
        "name": "Kuwaiti Dinar",
        "numeric_code": "414",
        "minor_units": 3,
        "countries": ["KW"],
    },
    "BHD": {
        "code": "BHD",
        "name": "Bahraini Dinar",
        "numeric_code": "048",
        "minor_units": 3,
        "countries": ["BH"],
    },
    "QAR": {
        "code": "QAR",
        "name": "Qatari Riyal",
        "numeric_code": "634",
        "minor_units": 2,
        "countries": ["QA"],
    },
    "OMR": {
        "code": "OMR",
        "name": "Omani Rial",
        "numeric_code": "512",
        "minor_units": 3,
        "countries": ["OM"],
    },
    "JOD": {
        "code": "JOD",
        "name": "Jordanian Dinar",
        "numeric_code": "400",
        "minor_units": 3,
        "countries": ["JO", "PS"],
    },
}

# Standard major currencies with high liquidity
G10_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK"}

# Common tradeable pairs with known typical spreads in basis points (bps)
COMMON_SPREAD_MAP: Dict[Tuple[str, str], int] = {
    ("EUR", "USD"): 8,
    ("USD", "EUR"): 8,
    ("GBP", "USD"): 10,
    ("USD", "GBP"): 10,
    ("USD", "JPY"): 8,
    ("JPY", "USD"): 9,
    ("USD", "CHF"): 12,
    ("CHF", "USD"): 12,
    ("USD", "CAD"): 10,
    ("CAD", "USD"): 10,
    ("AUD", "USD"): 12,
    ("USD", "AUD"): 12,
    ("NZD", "USD"): 15,
    ("USD", "NZD"): 15,
    ("EUR", "GBP"): 12,
    ("GBP", "EUR"): 12,
    ("EUR", "JPY"): 14,
    ("JPY", "EUR"): 15,
    ("EUR", "CHF"): 12,
    ("CHF", "EUR"): 12,
    ("USD", "SGD"): 18,
    ("SGD", "USD"): 18,
    ("USD", "HKD"): 14,
    ("HKD", "USD"): 14,
    ("USD", "MXN"): 35,
    ("USD", "BRL"): 45,
    ("USD", "INR"): 30,
    ("USD", "ZAR"): 40,
    ("USD", "TRY"): 75,
    ("USD", "AED"): 15,
    ("USD", "SAR"): 16,
    ("USD", "ILS"): 30,
    ("USD", "PLN"): 25,
    ("EUR", "PLN"): 25,
    ("USD", "SEK"): 22,
    ("USD", "NOK"): 22,
    ("USD", "THB"): 35,
    ("USD", "MYR"): 35,
    ("USD", "IDR"): 45,
    ("USD", "PHP"): 45,
    ("USD", "NGN"): 160,
    ("USD", "KES"): 140,
    ("USD", "EGP"): 130,
    ("USD", "VND"): 90,
    ("USD", "ARS"): 220,
}


def validate_currency(code: str) -> Tuple[bool, str]:
    """
    Validate whether a currency code conforms to active ISO 4217 specifications.

    Args:
        code: 3-letter currency code (e.g., 'USD', 'EUR').

    Returns:
        Tuple of (is_valid: bool, reason: str).
    """
    if not code or not isinstance(code, str):
        return False, "Currency code is missing or empty. Please specify a 3-letter ISO 4217 code."

    cleaned = code.strip().upper()
    if len(cleaned) != 3 or not cleaned.isalpha():
        return (
            False,
            f"Invalid currency code format '{cleaned}'. Must be a 3-letter alphabetic ISO 4217 code.",
        )

    if cleaned == "HRK":
        return (
            False,
            "HRK (Croatian Kuna) was retired on 1 January 2023 when Croatia adopted EUR. "
            "Please use EUR for payments to Croatia.",
        )

    if cleaned not in CURRENCIES:
        return (
            False,
            f"Currency code '{cleaned}' is not an active or supported ISO 4217 currency. "
            f"Please verify the 3-letter currency code.",
        )

    currency = CURRENCIES[cleaned]
    return True, f"Currency {cleaned} ({currency['name']}) is a valid ISO 4217 currency."


def get_currency_info(code: str) -> Dict[str, Any]:
    """
    Retrieve metadata for an ISO 4217 currency including minor units and valid countries.

    Args:
        code: 3-letter currency code.

    Returns:
        Dictionary containing currency attributes or empty dict if not found.
    """
    if not code:
        return {}
    cleaned = code.strip().upper()
    return CURRENCIES.get(cleaned, {})


def check_currency_pair_support(from_currency: str, to_currency: str) -> Dict[str, Any]:
    """
    Evaluate support, liquidity tier, and expected spread for a currency pair.

    Args:
        from_currency: 3-letter source currency code.
        to_currency: 3-letter target currency code.

    Returns:
        Dictionary detailing pair support, common_pair flag, spread bps, and liquidity tier.
    """
    from_clean = (from_currency or "").strip().upper()
    to_clean = (to_currency or "").strip().upper()

    from_valid, from_err = validate_currency(from_clean)
    to_valid, to_err = validate_currency(to_clean)

    if not from_valid or not to_valid:
        error_msg = from_err if not from_valid else to_err
        return {
            "supported": False,
            "pair": f"{from_clean}/{to_clean}",
            "from_currency": from_clean,
            "to_currency": to_clean,
            "common_pair": False,
            "typical_spread_bps": 0,
            "liquidity_tier": "UNSUPPORTED",
            "message": f"Currency pair validation failed: {error_msg}",
        }

    # Same currency: no conversion required
    if from_clean == to_clean:
        return {
            "supported": True,
            "pair": f"{from_clean}/{to_clean}",
            "from_currency": from_clean,
            "to_currency": to_clean,
            "common_pair": True,
            "typical_spread_bps": 0,
            "liquidity_tier": "SAME_CURRENCY",
            "message": f"No foreign exchange conversion needed for {from_clean}/{to_clean}.",
        }

    # Direct match in common spread map
    pair_tuple = (from_clean, to_clean)
    if pair_tuple in COMMON_SPREAD_MAP:
        spread = COMMON_SPREAD_MAP[pair_tuple]
        tier = "HIGH" if spread <= 20 else ("MEDIUM" if spread <= 50 else "EXOTIC")
        return {
            "supported": True,
            "pair": f"{from_clean}/{to_clean}",
            "from_currency": from_clean,
            "to_currency": to_clean,
            "common_pair": True,
            "typical_spread_bps": spread,
            "liquidity_tier": tier,
            "message": f"Direct currency corridor supported. Estimated interbank spread is ~{spread} bps.",
        }

    # G10 crosses (both in G10)
    if from_clean in G10_CURRENCIES and to_clean in G10_CURRENCIES:
        return {
            "supported": True,
            "pair": f"{from_clean}/{to_clean}",
            "from_currency": from_clean,
            "to_currency": to_clean,
            "common_pair": True,
            "typical_spread_bps": 20,
            "liquidity_tier": "HIGH",
            "message": f"Major cross pair supported with high liquidity. Estimated spread is ~20 bps.",
        }

    # Cross routing through USD or EUR
    is_exotic_corridor = from_clean in {"NGN", "KES", "EGP", "ARS", "VND"} or to_clean in {"NGN", "KES", "EGP", "ARS", "VND"}
    estimated_spread = 150 if is_exotic_corridor else 60
    liquidity = "EXOTIC" if is_exotic_corridor else "MODERATE"

    return {
        "supported": True,
        "pair": f"{from_clean}/{to_clean}",
        "from_currency": from_clean,
        "to_currency": to_clean,
        "common_pair": not is_exotic_corridor,
        "typical_spread_bps": estimated_spread,
        "liquidity_tier": liquidity,
        "message": (
            f"Triangulated FX conversion via USD/EUR clearing. "
            f"Estimated spread is ~{estimated_spread} bps due to lower bilateral liquidity."
        ),
    }
